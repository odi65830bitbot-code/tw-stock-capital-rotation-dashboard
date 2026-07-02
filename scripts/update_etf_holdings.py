#!/usr/bin/env python3
"""Normalize ETF constituent holdings exports into the dashboard data contract."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_ROOT = ROOT / "data" / "raw" / "etf_holdings"
DEFAULT_PROCESSED_PATH = ROOT / "data" / "processed" / "etf_holdings.parquet"

COLUMN_ALIASES = {
    "as_of_date": ["as_of_date", "date", "資料日期", "日期", "基準日", "持股日期"],
    "etf_code": ["etf_code", "etf_id", "ETF代號", "ETF 代號", "基金代號", "證券代號"],
    "etf_name": ["etf_name", "ETF名稱", "ETF 名稱", "基金名稱", "證券名稱"],
    "constituent_code": ["constituent_code", "stock_code", "成分股代號", "成份股代號", "持股代號", "股票代號"],
    "constituent_name": ["constituent_name", "stock_name", "成分股名稱", "成份股名稱", "持股名稱", "股票名稱"],
    "weight_pct": ["weight_pct", "weight", "權重", "權重(%)", "持股比例", "比例", "占比"],
    "shares": ["shares", "股數", "持有股數", "張數", "單位數"],
    "market_value_twd": ["market_value_twd", "market_value", "市值", "持有市值", "金額", "評價金額"],
    "source_url": ["source_url", "來源網址", "url", "URL"],
}


def _find_column(df: pd.DataFrame, canonical: str) -> str | None:
    aliases = {name.strip().lower(): name for name in df.columns}
    for candidate in COLUMN_ALIASES[canonical]:
        found = aliases.get(candidate.strip().lower())
        if found:
            return found
    return None


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace(",", "").replace("%", "").strip()
    if text in {"", "-", "--", "N/A", "None", "null"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _is_etf_code(value: Any) -> bool:
    code = str(value or "").strip().upper()
    return bool(re.match(r"^00[0-9A-Z]{2,4}$", code))


def normalize_holdings_frame(
    frame: pd.DataFrame,
    *,
    source: str,
    fallback_as_of_date: str | None = None,
    source_url: str | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if frame.empty:
        return pd.DataFrame(columns=_output_columns())

    columns = {name: _find_column(frame, name) for name in COLUMN_ALIASES}
    for _, raw in frame.iterrows():
        as_of_raw = raw.get(columns["as_of_date"]) if columns["as_of_date"] else fallback_as_of_date
        etf_code = str(raw.get(columns["etf_code"], "") if columns["etf_code"] else "").strip().upper()
        constituent_code = str(raw.get(columns["constituent_code"], "") if columns["constituent_code"] else "").strip()
        if not _is_etf_code(etf_code) or not constituent_code:
            continue
        rows.append(
            {
                "as_of_date": pd.to_datetime(as_of_raw, errors="coerce"),
                "etf_code": etf_code,
                "etf_name": str(raw.get(columns["etf_name"], "") if columns["etf_name"] else "").strip(),
                "constituent_code": constituent_code,
                "constituent_name": str(raw.get(columns["constituent_name"], "") if columns["constituent_name"] else "").strip(),
                "weight_pct": _parse_number(raw.get(columns["weight_pct"])) if columns["weight_pct"] else None,
                "shares": _parse_number(raw.get(columns["shares"])) if columns["shares"] else None,
                "market_value_twd": _parse_number(raw.get(columns["market_value_twd"])) if columns["market_value_twd"] else None,
                "source": source,
                "source_url": (
                    str(raw.get(columns["source_url"], "")).strip()
                    if columns["source_url"] and str(raw.get(columns["source_url"], "")).strip()
                    else source_url
                ),
            }
        )

    out = pd.DataFrame(rows, columns=_output_columns())
    if out.empty:
        return out
    out = out.dropna(subset=["as_of_date"])
    return out.sort_values(["as_of_date", "etf_code", "weight_pct"], ascending=[True, True, False], na_position="last").reset_index(drop=True)


def _output_columns() -> list[str]:
    return [
        "as_of_date",
        "etf_code",
        "etf_name",
        "constituent_code",
        "constituent_name",
        "weight_pct",
        "shares",
        "market_value_twd",
        "source",
        "source_url",
    ]


def _load_json_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ["records", "items", "holdings", "data"]:
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def load_raw_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".json":
        return pd.DataFrame(_load_json_records(path))
    raise ValueError(f"unsupported ETF holdings file: {path}")


def build_etf_holdings(raw_root: Path = DEFAULT_RAW_ROOT, processed_path: Path = DEFAULT_PROCESSED_PATH) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in sorted(raw_root.glob("**/*")):
        if path.suffix.lower() not in {".csv", ".json"}:
            continue
        raw = load_raw_file(path)
        normalized = normalize_holdings_frame(raw, source=path.name)
        if not normalized.empty:
            frames.append(normalized)

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=_output_columns())
    if not out.empty:
        out = (
            out.sort_values(["as_of_date", "etf_code", "constituent_code"])
            .drop_duplicates(["as_of_date", "etf_code", "constituent_code"], keep="last")
            .reset_index(drop=True)
        )
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(processed_path, index=False)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize ETF constituent holdings files.")
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_PROCESSED_PATH)
    args = parser.parse_args()

    out = build_etf_holdings(args.raw_root, args.output)
    print(f"ETF holdings rows={len(out)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
