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
    reader = csv.DictReader(io.StringIO(csv_text))
    return [{k: _parse_number_or_str(v) for k, v in row.items()} for row in reader]


def _records_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
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
        json_url = config.json_url
        csv_url = config.csv_url

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
