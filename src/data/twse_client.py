from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

from .official_source_registry import (
    SourceConfig,
    TWSE_DAILY_PRICE,
    TWSE_INDEX,
    TWSE_INSTITUTION_AMOUNT,
    TWSE_INSTITUTION_FLOW,
    TWSE_SECTOR_CLASSIFICATION,
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
    errors: List[str] = field(default_factory=list)


def _sanitize_text(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _clean_csv_cell(v: Any) -> str:
    text = _sanitize_text(v).replace("\ufeff", "")
    if text.startswith('="') and text.endswith('"'):
        return text[2:-1].strip()
    if text.startswith("="):
        return text[1:].strip().strip('"')
    return text


def _to_roc_date(d: date) -> str:
    return f"{d.year - 1911:03d}{d.month:02d}{d.day:02d}"


def _to_ad_from_roc(raw: str) -> date:
    if len(raw) != 7:
        raise ValueError(f"TWSE/TPEX 日期格式不符 (expected R.O.C. YYYYMMDD): {raw}")
    return date(int(raw[:3]) + 1911, int(raw[3:5]), int(raw[5:7]))


def _to_query_date(cfg: SourceConfig, target_date: date) -> str:
    if not cfg.supports_query_date:
        return ""
    if cfg.query_date_format == "roc":
        return _to_roc_date(target_date)
    if cfg.query_date_format == "gregorian":
        return target_date.strftime("%Y%m%d")
    return ""


def _interpolate_url(template: str, query_date: str) -> str:
    if "{" in template and "}" in template:
        return template.format(date=query_date)
    return template


def _decode_csv(raw: bytes) -> str:
    # TWSE 舊 API 常見 Big5；如有編碼偏差再退回其他編碼
    for encoding in ("utf-8-sig", "utf-8", "big5", "cp950", "latin1"):
        try:
            text = raw.decode(encoding)
            if "�" not in text:
                return text
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def _parse_csv_text(csv_text: str) -> List[Dict[str, Any]]:
    rows = [
        [_clean_csv_cell(cell) for cell in row]
        for row in csv.reader(io.StringIO(csv_text))
        if any(_sanitize_text(cell) for cell in row)
    ]
    if not rows:
        return []

    header_idx = 0
    for idx, row in enumerate(rows):
        non_empty = [cell for cell in row if cell]
        if len(non_empty) > 1:
            header_idx = idx
            break

    headers = rows[header_idx]
    while headers and not headers[-1]:
        headers = headers[:-1]
    if not headers:
        return []

    records: List[Dict[str, Any]] = []
    for raw_row in rows[header_idx + 1 :]:
        if raw_row[: len(headers)] == headers:
            continue
        row = raw_row + [""] * max(0, len(headers) - len(raw_row))
        record = {
            header: _clean_csv_cell(row[idx])
            for idx, header in enumerate(headers)
            if header
        }
        if any(record.values()):
            records.append(record)
    return records


def _records_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise ValueError("API 回傳資料格式不支援")

    stat = str(payload.get("stat", "")).strip()
    if stat and stat != "OK":
        raise ValueError(f"TWSE 回傳 stat 非預期: {stat}")

    tables = payload.get("tables")
    if isinstance(tables, list):
        payload_date = _sanitize_text(payload.get("date", ""))
        for table in tables:
            if not isinstance(table, dict):
                continue
            fields = table.get("fields", [])
            data = table.get("data", [])
            if not isinstance(fields, list) or not isinstance(data, list):
                continue
            field_set = {str(f) for f in fields}
            is_daily_price = {"證券代號", "證券名稱", "成交股數", "收盤價"}.issubset(field_set)
            if not is_daily_price:
                continue
            records = [
                {
                    **{str(f): _sanitize_text(v) for f, v in zip(fields, row, strict=False)},
                    "Date": payload_date,
                    "date": payload_date,
                }
                for row in data
                if isinstance(row, list)
            ]
            if records:
                return records

    # TWSE 典型 payload 有 fields + data（data 可能是 list-of-lists）
    data = payload.get("data")
    if isinstance(data, list):
        if not data:
            return []
        if isinstance(data[0], dict):
            return [dict(row) for row in data]
        if isinstance(data[0], list):
            fields = payload.get("fields", [])
            if isinstance(fields, list) and fields:
                return [
                    {str(f): _sanitize_text(v) for f, v in zip(fields, row, strict=False)}
                    for row in data
                    if len(row) <= len(fields) or True
                ]
            raise ValueError("缺少 fields 欄位，無法解析 list-of-lists")
    # 部分 endpoint 回傳完整 list-like object
    return [payload]


def _infer_date(records: Iterable[Dict[str, Any]], cfg: SourceConfig, fallback: date) -> date:
    raw_dates: set[str] = set()
    for row in records:
        value = _sanitize_text(row.get(cfg.date_key, ""))
        if value:
            raw_dates.add(value)
        else:
            alt_value = _sanitize_text(row.get("Date", ""))
            if alt_value:
                raw_dates.add(alt_value)

    if not raw_dates:
        return fallback

    roc_dates = {_to_ad_from_roc(v) for v in raw_dates if v.isdigit() and len(v) == 7}
    yyyy_dates = {_sanitize_text(v) for v in raw_dates if v.isdigit() and len(v) == 8}
    if yyyy_dates:
        yyyy = max(date(int(v[:4]), int(v[4:6]), int(v[6:8])) for v in yyyy_dates)
        return yyyy
    if roc_dates:
        return max(roc_dates)
    return fallback


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


def _request_json_resp(url: str, session: requests.Session, timeout: int) -> Any:
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "").lower()
    if "text/csv" in content_type or resp.text.strip().startswith("<"):
        raise ValueError(f"預期 JSON 卻回傳非 JSON，content-type={content_type}")
    return resp.json()


def _request_csv_resp(url: str, session: requests.Session, timeout: int) -> str:
    resp = session.get(url, headers={"Accept": "text/csv"}, timeout=timeout)
    resp.raise_for_status()
    return _decode_csv(resp.content)


class TWSEClient:
    """TWSE 抓取器：官方 JSON 為主，僅在失敗時使用官方 CSV fallback。"""

    def __init__(
        self,
        *,
        raw_root: Path,
        timeout: int = 30,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.raw_root = Path(raw_root)
        self.session = session or requests.Session()
        self.timeout = timeout
        self.raw_root.mkdir(parents=True, exist_ok=True)
        LOGGER.info("初始化 TWSEClient raw_root=%s", self.raw_root)

    def _load_cached(self, config: SourceConfig, target_date: date) -> FetchResult | None:
        day_dir = self.raw_root / config.market / target_date.strftime("%Y%m%d")
        json_path = day_dir / f"{config.name}.json"
        csv_path = day_dir / f"{config.name}.csv"
        if not json_path.exists():
            return None
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        records = _records_from_payload(payload)
        if config.name.startswith("twse_institutional"):
            for row in records:
                if isinstance(row, dict) and not row.get(config.date_key):
                    row[config.date_key] = target_date.strftime("%Y%m%d")
        return FetchResult(
            dataset=config.name,
            trade_date=target_date,
            raw_json_path=json_path,
            raw_csv_path=csv_path if csv_path.exists() else None,
            records=records,
            source=config.market,
        )

    def _fetch_dataset(self, config: SourceConfig, target_date: date) -> FetchResult:
        cached = self._load_cached(config, target_date)
        if cached is not None:
            return cached

        query_date = _to_query_date(config, target_date)
        json_url = _interpolate_url(config.json_url, query_date)
        csv_url = _interpolate_url(config.csv_url, query_date)
        errors: List[str] = []

        # 1) 先抓 JSON（官方 OpenAPI 或官方 json endpoint）
        try:
            payload = _request_json_resp(json_url, self.session, self.timeout)
            records = _records_from_payload(payload)
            if not records:
                raise ValueError("解析後的資料筆數為 0")
            # 某些 TWSE legacy response（如法人買賣超）將 date 放在 payload 層級，不在每列。
            if isinstance(payload, dict) and config.date_key not in records[0] and config.date_key in payload:
                for row in records:
                    if isinstance(row, dict) and config.date_key not in row:
                        row[config.date_key] = payload[config.date_key]
            effective_date = _infer_date(records, config, target_date)
            if config.supports_query_date and effective_date != target_date:
                raise ValueError(f"TWSE 回傳日期 {effective_date} 與查詢日期 {target_date} 不一致")
            raw_csv_text = _to_csv_text(records)
            return self._save_raw(
                config.market,
                effective_date,
                config.name,
                payload,
                records,
                raw_csv_text,
            )
        except Exception as exc:
            msg = f"json primary 失敗 ({config.name}): {type(exc).__name__}: {exc}"
            LOGGER.error(msg)
            errors.append(msg)

        # 2) fallback 到官方 CSV
        try:
            raw_csv_text = _request_csv_resp(csv_url, self.session, self.timeout)
            records = _parse_csv_text(raw_csv_text)
            if not records:
                raise ValueError("CSV 解析後資料筆數為 0")
            payload = records
            # CSV 欄位不一定有 date，若外層有日子可補進去
            if config.date_key and records and config.date_key not in records[0]:
                for row in records:
                    if config.name.startswith("twse_institutional") and not row.get(config.date_key):
                        row[config.date_key] = target_date.strftime("%Y%m%d")
            effective_date = _infer_date(records, config, target_date)
            if config.supports_query_date and effective_date != target_date:
                raise ValueError(f"TWSE CSV 回傳日期 {effective_date} 與查詢日期 {target_date} 不一致")
            # 仍保留 raw_json 與 raw_csv
            return self._save_raw(
                config.market,
                effective_date,
                config.name,
                payload,
                records,
                raw_csv_text,
                used_fallback=True,
            )
        except Exception as exc:
            msg = f"official csv fallback 失敗 ({config.name}): {type(exc).__name__}: {exc}"
            LOGGER.error(msg)
            errors.append(msg)

        raise RuntimeError(f"{config.name} 全部官方來源失敗: " + "; ".join(errors))

    def _save_raw(
        self,
        market: str,
        trade_date: date,
        dataset: str,
        payload: Any,
        records: List[Dict[str, Any]],
        csv_text: str,
        *,
        used_fallback: bool = False,
    ) -> FetchResult:
        day_dir = self.raw_root / market / trade_date.strftime("%Y%m%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        json_path = day_dir / f"{dataset}.json"
        csv_path = day_dir / f"{dataset}.csv"

        json_payload = payload
        if used_fallback and not isinstance(payload, (dict, list)):
            json_payload = {"data": payload}
        json_path.write_text(
            json.dumps(json_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        csv_path.write_text(csv_text or "", encoding="utf-8")
        return FetchResult(
            dataset=dataset,
            trade_date=trade_date,
            raw_json_path=json_path,
            raw_csv_path=csv_path,
            records=records,
            source=market,
        )

    def fetch_daily_price(self, trade_date: date) -> FetchResult:
        return self._fetch_dataset(TWSE_DAILY_PRICE, trade_date)

    def fetch_institutional_flow(self, trade_date: date) -> FetchResult:
        return self._fetch_dataset(TWSE_INSTITUTION_FLOW, trade_date)

    def fetch_institutional_amount(self, trade_date: date) -> FetchResult:
        return self._fetch_dataset(TWSE_INSTITUTION_AMOUNT, trade_date)

    def fetch_sector_classification(self, trade_date: date) -> FetchResult:
        return self._fetch_dataset(TWSE_SECTOR_CLASSIFICATION, trade_date)

    def fetch_index(self, trade_date: date) -> FetchResult:
        return self._fetch_dataset(TWSE_INDEX, trade_date)

    def fetch_all(self, trade_date: date) -> Dict[str, FetchResult]:
        return {
            "daily_price": self.fetch_daily_price(trade_date),
            "institutional_flow": self.fetch_institutional_flow(trade_date),
            "institutional_amount": self.fetch_institutional_amount(trade_date),
            "sector_classification": self.fetch_sector_classification(trade_date),
            "index": self.fetch_index(trade_date),
        }


__all__ = ["TWSEClient", "FetchResult"]
