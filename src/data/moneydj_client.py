from __future__ import annotations

import csv
import io
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import urllib3
from requests.exceptions import SSLError
from urllib3.exceptions import InsecureRequestWarning


LOGGER = logging.getLogger(__name__)
urllib3.disable_warnings(InsecureRequestWarning)

MONEYDJ_MARKET_FUND_FLOW_URL = "https://www.moneydj.com/z/zb/zba/zba.djhtm"
MONEYDJ_SECTOR_HISTORY_URL = "https://www.moneydj.com/Z/ZB/ZBA/CZBA1.DJBCD?a={sector_id}"


@dataclass
class MoneyDJFetchResult:
    dataset: str
    trade_date: date
    raw_json_path: Path
    raw_csv_path: Path
    raw_html_path: Path
    records: List[Dict[str, Any]]
    history_records: List[Dict[str, Any]] = field(default_factory=list)
    source: str = "moneydj"
    errors: List[str] = field(default_factory=list)


class _TableTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.cells: list[str] = []
        self._capture = False
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"td", "th"}:
            self._capture = True
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"td", "th"} and self._capture:
            text = " ".join("".join(self._buf).split())
            if text:
                self.cells.append(text)
            self._capture = False
            self._buf = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buf.append(data)


def _decode_moneydj(content: bytes) -> str:
    for encoding in ("big5", "cp950", "utf-8-sig", "utf-8"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("big5", errors="ignore")


def _parse_pct(text: str) -> float | None:
    cleaned = text.replace("%", "").replace(",", "").strip()
    if cleaned in {"", "-", "--"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_float(text: str) -> float | None:
    cleaned = str(text).replace(",", "").strip()
    if cleaned in {"", "-", "--"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _infer_update_date(html: str, target_date: date) -> date:
    match = re.search(r"最後更新時間：\s*(\d{1,2})/(\d{1,2})", html)
    if not match:
        return target_date
    month = int(match.group(1))
    day = int(match.group(2))
    inferred = date(target_date.year, month, day)
    if inferred > target_date:
        inferred = date(target_date.year - 1, month, day)
    return inferred


def _parse_sector_catalog(html: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    pattern = re.compile(r"s(TSE|OTC)\[\d+\]\s*=\s*new\s+SecEnt\('([^']+)'\s*,\s*'([^']+)'\)")
    for market_raw, sector_id, industry in pattern.findall(html):
        records.append(
            {
                "market": "TWSE" if market_raw == "TSE" else "TPEX",
                "moneydj_sector_id": sector_id,
                "industry": industry.strip(),
            }
        )
    return records


def _moneydj_mmdd_to_date(raw: str, target_date: date) -> date | None:
    text = str(raw).strip()
    if not text.isdigit():
        return None
    if len(text) == 3:
        month = int(text[0])
        day = int(text[1:])
    elif len(text) == 4:
        month = int(text[:2])
        day = int(text[2:])
    else:
        return None
    try:
        inferred = date(target_date.year, month, day)
    except ValueError:
        return None
    if inferred > target_date:
        inferred = date(target_date.year - 1, month, day)
    return inferred


def _parse_bcd_history(
    text: str,
    *,
    target_date: date,
    market: str,
    industry: str,
    sector_id: str,
) -> list[dict[str, Any]]:
    parts = text.strip().split()
    if len(parts) < 4:
        return []

    dates = parts[0].split(",")
    market_values = parts[1].split(",")
    sector_values = parts[2].split(",")
    flow_rates = parts[3].split(",")
    row_count = min(len(dates), len(market_values), len(sector_values), len(flow_rates))

    rows: list[dict[str, Any]] = []
    for i in range(row_count):
        trade_date = _moneydj_mmdd_to_date(dates[i], target_date)
        if trade_date is None:
            continue
        rows.append(
            {
                "trade_date": trade_date.strftime("%Y-%m-%d"),
                "market": market,
                "industry": industry,
                "moneydj_sector_id": sector_id,
                "moneydj_market_index": _parse_float(market_values[i]),
                "moneydj_sector_index": _parse_float(sector_values[i]),
                "moneydj_flow_rate_pct": _parse_float(flow_rates[i]),
                "source": "moneydj",
                "source_url": MONEYDJ_SECTOR_HISTORY_URL.format(sector_id=sector_id),
            }
        )
    return rows


def _parse_market_fund_flow(html: str, target_date: date) -> tuple[date, list[dict[str, Any]]]:
    parser = _TableTextParser()
    parser.feed(html)
    cells = parser.cells
    trade_date = _infer_update_date(html, target_date)

    records: list[dict[str, Any]] = []
    market: str | None = None
    i = 0
    while i < len(cells):
        cell = cells[i]
        if "上市資金流向表" in cell:
            market = "TWSE"
            i += 1
            continue
        if "上櫃資金流向表" in cell:
            market = "TPEX"
            i += 1
            continue
        if cell in {"類股名稱", "流向率"} or cell == "\xa0":
            i += 1
            continue
        if market and i + 1 < len(cells):
            rate_text = cells[i + 1]
            rate = _parse_pct(rate_text)
            if rate is not None:
                records.append(
                    {
                        "trade_date": trade_date.strftime("%Y-%m-%d"),
                        "market": market,
                        "industry": cell.strip(),
                        "moneydj_flow_rate_pct": rate,
                        "source": "moneydj",
                        "source_url": MONEYDJ_MARKET_FUND_FLOW_URL,
                    }
                )
                i += 2
                continue
        i += 1
    return trade_date, records


def _to_csv_text(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    fieldnames: list[str] = []
    for row in records:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(records)
    return out.getvalue()


def _pct_change(first: float | None, last: float | None) -> float | None:
    if first is None or last is None or first == 0:
        return None
    return (last / first - 1.0) * 100.0


def _avg(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _build_best_indicators(
    table_records: list[dict[str, Any]],
    history_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    history_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in history_records:
        key = (str(row["market"]), str(row["industry"]))
        history_by_key.setdefault(key, []).append(row)
    for rows in history_by_key.values():
        rows.sort(key=lambda r: str(r["trade_date"]))

    indicator_rows: list[dict[str, Any]] = []
    for row in table_records:
        key = (str(row["market"]), str(row["industry"]))
        history = history_by_key.get(key, [])
        flow_values = [
            float(r["moneydj_flow_rate_pct"])
            for r in history
            if r.get("moneydj_flow_rate_pct") is not None
        ]
        latest_history = history[-1] if history else {}
        latest_from_table = row.get("moneydj_flow_rate_pct")
        latest_from_history = latest_history.get("moneydj_flow_rate_pct")

        validation_status = "warning"
        validation_message = "缺少 MoneyDJ 明細圖歷史資料"
        if latest_from_table is not None and latest_from_history is not None:
            diff = abs(float(latest_from_table) - float(latest_from_history))
            if diff <= 0.05:
                validation_status = "pass"
                validation_message = f"表格與明細圖最新流向率差異 {diff:.2f} pct"
            else:
                validation_status = "warning"
                validation_message = f"表格與明細圖最新流向率差異偏大 {diff:.2f} pct"

        last_5 = flow_values[-5:]
        last_20 = flow_values[-20:]
        flow_5d_avg = _avg(last_5)
        flow_20d_avg = _avg(last_20)
        sector_idx = [r.get("moneydj_sector_index") for r in history if r.get("moneydj_sector_index") is not None]
        market_idx = [r.get("moneydj_market_index") for r in history if r.get("moneydj_market_index") is not None]
        sector_return_20d = _pct_change(sector_idx[-20], sector_idx[-1]) if len(sector_idx) >= 20 else None
        market_return_20d = _pct_change(market_idx[-20], market_idx[-1]) if len(market_idx) >= 20 else None
        relative_strength_20d = (
            sector_return_20d - market_return_20d
            if sector_return_20d is not None and market_return_20d is not None
            else None
        )

        enriched = dict(row)
        enriched.update(
            {
                "moneydj_history_points": len(history),
                "moneydj_history_latest_flow_rate_pct": latest_from_history,
                "moneydj_flow_rate_5d_avg_pct": flow_5d_avg,
                "moneydj_flow_rate_20d_avg_pct": flow_20d_avg,
                "moneydj_flow_rate_accel_pct": (
                    flow_5d_avg - flow_20d_avg
                    if flow_5d_avg is not None and flow_20d_avg is not None
                    else None
                ),
                "moneydj_flow_rate_5d_change_pct": (
                    flow_values[-1] - flow_values[-5]
                    if len(flow_values) >= 5
                    else None
                ),
                "moneydj_sector_return_20d_pct": sector_return_20d,
                "moneydj_market_return_20d_pct": market_return_20d,
                "moneydj_relative_strength_20d_pct": relative_strength_20d,
                "moneydj_validation_status": validation_status,
                "moneydj_validation_message": validation_message,
            }
        )
        indicator_rows.append(enriched)
    return indicator_rows


class MoneyDJClient:
    """MoneyDJ supplemental fetcher.

    MoneyDJ is intentionally kept outside the official TWSE/TPEX source registry.
    The dashboard may use it as supplemental sector context, never as official data.
    """

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

    def _get(self, url: str, headers: dict[str, str], errors: list[str]) -> requests.Response:
        try:
            response = self.session.get(url, timeout=self.timeout, headers=headers)
        except SSLError as exc:
            msg = "MoneyDJ SSL verification failed; retried with verify=false"
            if msg not in errors:
                errors.append(msg)
                LOGGER.warning("%s: %s", msg, exc)
            response = self.session.get(url, timeout=self.timeout, headers=headers, verify=False)
        response.raise_for_status()
        return response

    def fetch_market_fund_flow(self, target_date: date) -> MoneyDJFetchResult:
        errors: list[str] = []
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.moneydj.com/",
        }
        response = self._get(MONEYDJ_MARKET_FUND_FLOW_URL, headers, errors)
        html = _decode_moneydj(response.content)
        trade_date, table_records = _parse_market_fund_flow(html, target_date)
        if not table_records:
            raise RuntimeError("MoneyDJ market fund flow parsed 0 rows")
        sector_catalog = _parse_sector_catalog(html)

        history_records: list[dict[str, Any]] = []
        history_headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": MONEYDJ_MARKET_FUND_FLOW_URL,
        }
        for item in sector_catalog:
            url = MONEYDJ_SECTOR_HISTORY_URL.format(sector_id=item["moneydj_sector_id"])
            try:
                history_resp = self._get(url, history_headers, errors)
                history_records.extend(
                    _parse_bcd_history(
                        history_resp.text,
                        target_date=target_date,
                        market=item["market"],
                        industry=item["industry"],
                        sector_id=item["moneydj_sector_id"],
                    )
                )
            except Exception as exc:
                msg = f"MoneyDJ sector history failed {item['moneydj_sector_id']}: {type(exc).__name__}: {exc}"
                LOGGER.warning(msg)
                errors.append(msg)

        records = _build_best_indicators(table_records, history_records)

        day_dir = self.raw_root / "moneydj" / trade_date.strftime("%Y%m%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        dataset = "moneydj_market_fund_flow"
        html_path = day_dir / f"{dataset}.html"
        json_path = day_dir / f"{dataset}.json"
        csv_path = day_dir / f"{dataset}.csv"
        history_csv_path = day_dir / "moneydj_sector_flow_history.csv"

        html_path.write_text(html, encoding="utf-8")
        payload = {
            "dataset": dataset,
            "source": "moneydj",
            "source_url": MONEYDJ_MARKET_FUND_FLOW_URL,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "target_date": target_date.isoformat(),
            "trade_date": trade_date.isoformat(),
            "errors": errors,
            "sector_catalog": sector_catalog,
            "records": records,
            "history_records": history_records,
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        csv_path.write_text(_to_csv_text(records), encoding="utf-8")
        history_csv_path.write_text(_to_csv_text(history_records), encoding="utf-8")

        return MoneyDJFetchResult(
            dataset=dataset,
            trade_date=trade_date,
            raw_json_path=json_path,
            raw_csv_path=csv_path,
            raw_html_path=html_path,
            records=records,
            history_records=history_records,
            errors=errors,
        )


__all__ = [
    "MoneyDJClient",
    "MoneyDJFetchResult",
    "_parse_bcd_history",
    "_parse_market_fund_flow",
    "_parse_sector_catalog",
]
