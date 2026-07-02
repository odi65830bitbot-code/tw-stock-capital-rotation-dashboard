from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

from .official_source_registry import (
    SourceConfig,
    TPEX_DAILY_PRICE,
    TPEX_INDEX,
    TPEX_50_INDEX,
    TPEX_INSTITUTION_AMOUNT,
    TPEX_INSTITUTION_FLOW,
    TPEX_SECTOR_CLASSIFICATION,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class FetchResult:
    dataset: str
    trade_date: date
    raw_json_path: Path
    raw_csv_path: Path | None
    records: List[Dict[str, Any]]
    source: str
    errors: List[str] | None = None


def _sanitize_text(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _parse_number_or_str(v: Any) -> str:
    return _sanitize_text(v)


def _decode_csv(raw: bytes) -> str:
    return raw.decode("utf-8", errors="ignore")


def _to_csv_text(records: List[Dict[str, Any]]) -> str:
    if not records:
        return ""
    fieldnames: List[str] = []
    for row in records:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue()


def _parse_csv_text(csv_text: str) -> List[Dict[str, Any]]:
    lines = csv_text.splitlines()
    if not lines:
        return []
    
    # 智慧判斷是否跳過第一行說明標題：若第一行逗號小於 3 且第二行逗號大於等於 3，代表第一行是標題說明
    first_line_cols = len(lines[0].split(","))
    second_line_cols = len(lines[1].split(",")) if len(lines) > 1 else 0
    
    start_idx = 0
    if first_line_cols < 3 and second_line_cols >= 3:
        start_idx = 1
        
    clean_csv = "\n".join(lines[start_idx:])
    reader = csv.DictReader(io.StringIO(clean_csv))
    return [{k: _parse_number_or_str(v) for k, v in row.items()} for row in reader]



def _records_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if "tables" in payload and isinstance(payload["tables"], list) and len(payload["tables"]) > 0:
            date_val = payload.get("date", payload["tables"][0].get("date", ""))
            records = []
            for row in payload["tables"][0].get("data", []):
                if len(row) >= 24:
                    records.append({
                        "Date": date_val,
                        "SecuritiesCompanyCode": row[0],
                        "CompanyName": row[1],
                        "ForeignBuy": row[8],
                        "ForeignSell": row[9],
                        "ForeignNetBuy": row[10],
                        "TrustBuy": row[11],
                        "TrustSell": row[12],
                        "TrustNetBuy": row[13],
                        "DealerBuy": row[20],
                        "DealerSell": row[21],
                        "DealerNetBuy": row[22],
                        "NetBuy": row[23]
                    })
            return records

        if "aaData" in payload:
            date_val = payload.get("date", "")
            records = []
            for row in payload["aaData"]:
                if len(row) >= 24:
                    records.append({
                        "Date": date_val,
                        "SecuritiesCompanyCode": row[0],
                        "CompanyName": row[1],
                        "ForeignBuy": row[8],
                        "ForeignSell": row[9],
                        "ForeignNetBuy": row[10],
                        "TrustBuy": row[11],
                        "TrustSell": row[12],
                        "TrustNetBuy": row[13],
                        "DealerBuy": row[20],
                        "DealerSell": row[21],
                        "DealerNetBuy": row[22],
                        "NetBuy": row[23]
                    })
            return records
        error_hint = payload.get("error") if isinstance(payload.get("error"), str) else ""
        if error_hint:
            raise ValueError(f"TPEX 回傳錯誤: {error_hint}")
        data = payload.get("data")
        if isinstance(data, list):
            return data
        return [payload]
    raise ValueError("API 回傳格式不支援")


def _get_with_official_ssl_retry(
    session: requests.Session,
    url: str,
    *,
    timeout: int,
    headers: Dict[str, str] | None = None,
) -> requests.Response:
    try:
        return session.get(url, headers=headers, timeout=timeout)
    except requests.exceptions.SSLError as exc:
        LOGGER.warning("TPEX official SSL verification failed; retrying official URL with verify=false: %s", exc)
        return session.get(url, headers=headers, timeout=timeout, verify=False)


def _to_ad_date(raw: str) -> date:
    if len(raw) == 7 and raw.isdigit():
        return date(int(raw[:3]) + 1911, int(raw[3:5]), int(raw[5:7]))
    if len(raw) == 8 and raw.isdigit():
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    raise ValueError(f"日期格式無法解析: {raw}")


def _infer_date(records: Iterable[Dict[str, Any]], cfg: SourceConfig, fallback: date) -> date:
    values: set[str] = set()
    for row in records:
        v = _sanitize_text(row.get(cfg.date_key, ""))
        if v:
            values.add(v)
    if not values:
        return fallback
    date_values = [_to_ad_date(v) for v in values if v]
    if not date_values:
        return fallback
    return max(date_values)


def _to_roc_slash_date(target_date: date) -> str:
    y = target_date.year - 1911
    return f"{y:03d}/{target_date.month:02d}/{target_date.day:02d}"


def _to_query_date(cfg: SourceConfig, target_date: date) -> str:
    if not cfg.supports_query_date:
        return ""
    if cfg.query_date_format == "roc_slash":
        return _to_roc_slash_date(target_date)
    return ""


def _interpolate_url(template: str, query_date: str) -> str:
    if "{" in template and "}" in template:
        return template.format(date=query_date)
    return template


def _request_json_resp(url: str, session: requests.Session, timeout: int) -> Any:
    resp = _get_with_official_ssl_retry(session, url, timeout=timeout)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "").lower()
    if "text/csv" in content_type or resp.text.strip().startswith("<"):
        raise ValueError(f"預期 JSON 卻取得非 JSON: content-type={content_type}")
    return resp.json()


def _request_csv_resp(url: str, session: requests.Session, timeout: int) -> str:
    resp = _get_with_official_ssl_retry(session, url, headers={"Accept": "text/csv"}, timeout=timeout)
    resp.raise_for_status()
    return _decode_csv(resp.content)


class TPEXClient:
    def __init__(
        self,
        *,
        raw_root: Path,
        timeout: int = 30,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.raw_root = Path(raw_root)
        self.timeout = timeout
        self.session = session or requests.Session()
        self.raw_root.mkdir(parents=True, exist_ok=True)

    def _load_cached(self, config: SourceConfig, trade_date: date) -> FetchResult | None:
        day_dir = self.raw_root / "tpex" / trade_date.strftime("%Y%m%d")
        json_path = day_dir / f"{config.name}.json"
        csv_path = day_dir / f"{config.name}.csv"
        if not json_path.exists():
            return None
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        return FetchResult(
            dataset=config.name,
            trade_date=trade_date,
            raw_json_path=json_path,
            raw_csv_path=csv_path if csv_path.exists() else None,
            records=_records_from_payload(payload),
            source="tpex",
            errors=[],
        )

    def _save_raw(
        self,
        trade_date: date,
        dataset: str,
        payload: Any,
        csv_text: str,
    ) -> FetchResult:
        day_dir = self.raw_root / "tpex" / trade_date.strftime("%Y%m%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        json_path = day_dir / f"{dataset}.json"
        csv_path = day_dir / f"{dataset}.csv"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        csv_path.write_text(csv_text or "", encoding="utf-8")
        return FetchResult(
            dataset=dataset,
            trade_date=trade_date,
            raw_json_path=json_path,
            raw_csv_path=csv_path,
            records=_records_from_payload(payload),
            source="tpex",
            errors=[],
        )

    def _fetch(self, config: SourceConfig, trade_date: date) -> FetchResult:
        cached = self._load_cached(config, trade_date)
        if cached is not None:
            return cached

        errors: List[str] = []
        query_date = _to_query_date(config, trade_date)
        json_url = _interpolate_url(config.json_url, query_date)
        csv_url = _interpolate_url(config.csv_url, query_date)

        # 先抓 JSON
        try:
            payload = _request_json_resp(json_url, self.session, self.timeout)
            records = _records_from_payload(payload)
            if not records:
                raise ValueError("解析後資料筆數為 0")
            effective_date = _infer_date(records, config, trade_date)
            csv_text = _to_csv_text(records)
            return self._save_raw(effective_date, config.name, payload, csv_text)
        except Exception as exc:
            msg = f"{config.name} json primary 失敗: {type(exc).__name__}: {exc}"
            LOGGER.error(msg)
            errors.append(msg)

        # 官方 CSV fallback
        try:
            csv_text = _request_csv_resp(csv_url, self.session, self.timeout)
            records = _parse_csv_text(csv_text)
            if not records:
                raise ValueError("CSV 解析後資料筆數為 0")
            effective_date = _infer_date(records, config, trade_date)
            
            # 手動將 Date 補到每一列中，以備後續歸一化使用
            date_str = effective_date.strftime("%Y%m%d")
            for r in records:
                if "Date" not in r:
                    r["Date"] = date_str
                    
            return self._save_raw(effective_date, config.name, records, csv_text)
        except Exception as exc:
            msg = f"{config.name} official csv fallback 失敗: {type(exc).__name__}: {exc}"
            LOGGER.error(msg)
            errors.append(msg)

        raise RuntimeError(f"{config.name} 全部官方來源失敗: {'; '.join(errors)}")

    def fetch_daily_price(self, trade_date: date) -> FetchResult:
        return self._fetch(TPEX_DAILY_PRICE, trade_date)

    def fetch_institutional_flow(self, trade_date: date) -> FetchResult:
        return self._fetch(TPEX_INSTITUTION_FLOW, trade_date)

    def fetch_institutional_amount(self, trade_date: date) -> FetchResult:
        return self._fetch(TPEX_INSTITUTION_AMOUNT, trade_date)

    def fetch_sector_classification(self, trade_date: date) -> FetchResult:
        return self._fetch(TPEX_SECTOR_CLASSIFICATION, trade_date)

    def fetch_index(self, trade_date: date) -> FetchResult:
        return self._fetch(TPEX_INDEX, trade_date)

    def fetch_index_50(self, trade_date: date) -> FetchResult:
        return self._fetch(TPEX_50_INDEX, trade_date)

    def fetch_all(self, trade_date: date) -> Dict[str, FetchResult]:
        return {
            "daily_price": self.fetch_daily_price(trade_date),
            "institutional_flow": self.fetch_institutional_flow(trade_date),
            "institutional_amount": self.fetch_institutional_amount(trade_date),
            "sector_classification": self.fetch_sector_classification(trade_date),
            "index": self.fetch_index(trade_date),
            "index_50": self.fetch_index_50(trade_date),
        }


__all__ = ["TPEXClient", "FetchResult"]
