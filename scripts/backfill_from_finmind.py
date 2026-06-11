#!/usr/bin/env python3
"""Backfill formal processed datasets from local FinMind history."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
TAIPEI = ZoneInfo("Asia/Taipei")


def _now_iso() -> str:
    return datetime.now(TAIPEI).replace(microsecond=0).isoformat()


def _read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _date_text(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y-%m-%d")


def _stock_code(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(4)


def _is_common_stock(series: pd.Series) -> pd.Series:
    codes = _stock_code(series)
    return codes.str.match(r"^\d{4}$") & ~codes.str.startswith("0")


def _to_number(frame: pd.DataFrame, column: str, default: float | None = None) -> pd.Series:
    if column in frame.columns:
        return pd.to_numeric(frame[column], errors="coerce")
    return pd.Series(default, index=frame.index, dtype="float64")


def _mapping_from_existing(*frames: pd.DataFrame, column: str) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for frame in frames:
        if frame.empty or "stock_code" not in frame.columns or column not in frame.columns:
            continue
        for row in frame[["stock_code", column]].dropna().itertuples(index=False):
            code = str(row.stock_code).strip()
            if code and code not in mapping:
                mapping[code] = getattr(row, column)
    return mapping


def _market_from_existing(frame: pd.DataFrame, market_map: dict[str, Any]) -> pd.Series:
    mapped = frame["stock_code"].map(market_map)
    if "market" not in frame.columns:
        return mapped.fillna("UNKNOWN")
    current = frame["market"]
    has_current = current.notna() & current.astype(str).str.strip().ne("")
    return current.where(has_current, mapped).fillna("UNKNOWN")


def _prepare_price(finmind_price: pd.DataFrame, existing_daily: pd.DataFrame) -> pd.DataFrame:
    if finmind_price.empty:
        return pd.DataFrame()
    frame = finmind_price.copy()
    if "stock_code" not in frame.columns and "stock_id" in frame.columns:
        frame = frame.rename(columns={"stock_id": "stock_code"})
    elif "stock_id" in frame.columns:
        frame["stock_code"] = frame["stock_code"].fillna(frame["stock_id"])
    date_column = "trade_date" if "trade_date" in frame.columns else "date"
    frame["trade_date"] = _date_text(frame[date_column])
    frame["stock_code"] = _stock_code(frame["stock_code"])
    frame = frame[_is_common_stock(frame["stock_code"])].copy()
    frame = frame.dropna(subset=["trade_date", "stock_code"])

    market_map = _mapping_from_existing(existing_daily, column="market")
    name_map = _mapping_from_existing(existing_daily, column="stock_name")
    frame["market"] = _market_from_existing(frame, market_map)
    if "stock_name" not in frame.columns:
        frame["stock_name"] = frame["stock_code"].map(name_map).fillna("")
    else:
        frame["stock_name"] = frame["stock_name"].fillna(frame["stock_code"].map(name_map)).fillna("")

    frame["high"] = _to_number(frame, "high")
    if "max" in frame.columns:
        frame["high"] = frame["high"].fillna(_to_number(frame, "max"))
    frame["low"] = _to_number(frame, "low")
    if "min" in frame.columns:
        frame["low"] = frame["low"].fillna(_to_number(frame, "min"))
    frame["change"] = _to_number(frame, "change")
    if "spread" in frame.columns:
        frame["change"] = frame["change"].fillna(_to_number(frame, "spread"))

    output = pd.DataFrame(
        {
            "trade_date": frame["trade_date"],
            "market": frame["market"],
            "stock_code": frame["stock_code"],
            "stock_name": frame["stock_name"],
            "open": _to_number(frame, "open"),
            "high": frame["high"],
            "low": frame["low"],
            "close": _to_number(frame, "close"),
            "change": frame["change"],
            "trade_volume": _to_number(frame, "trade_volume").fillna(_to_number(frame, "Trading_Volume")),
            "trade_value_twd": _to_number(frame, "trade_value_twd").fillna(_to_number(frame, "Trading_money")),
            "transactions": _to_number(frame, "transactions").fillna(_to_number(frame, "Trading_turnover")),
        }
    )
    return output.dropna(subset=["trade_date", "stock_code", "close"])


def _institution_category(name: Any) -> str | None:
    text = str(name or "").lower()
    if "foreign" in text:
        return "foreign_net_shares"
    if "investment_trust" in text or "trustee" in text or "trust" in text:
        return "trustee_net_shares"
    if "dealer" in text:
        return "dealer_net_shares"
    return None


def _prepare_institutional(finmind_institutional: pd.DataFrame, existing_flow: pd.DataFrame) -> pd.DataFrame:
    if finmind_institutional.empty:
        return pd.DataFrame()
    frame = finmind_institutional.copy()
    if "stock_code" not in frame.columns and "stock_id" in frame.columns:
        frame = frame.rename(columns={"stock_id": "stock_code"})
    elif "stock_id" in frame.columns:
        frame["stock_code"] = frame["stock_code"].fillna(frame["stock_id"])
    date_column = "trade_date" if "trade_date" in frame.columns else "date"
    frame["trade_date"] = _date_text(frame[date_column])
    frame["stock_code"] = _stock_code(frame["stock_code"])
    frame = frame[_is_common_stock(frame["stock_code"])].copy()
    frame = frame.dropna(subset=["trade_date", "stock_code"])

    required = ["foreign_net_shares", "trustee_net_shares", "dealer_net_shares"]
    if not set(required).issubset(frame.columns):
        if not {"name", "buy", "sell"}.issubset(frame.columns):
            return pd.DataFrame()
        long_frame = frame.copy()
        long_frame["category"] = long_frame["name"].map(_institution_category)
        long_frame = long_frame.dropna(subset=["category"])
        long_frame["net_shares"] = _to_number(long_frame, "buy").fillna(0) - _to_number(long_frame, "sell").fillna(0)
        frame = (
            long_frame.pivot_table(
                index=["trade_date", "stock_code"],
                columns="category",
                values="net_shares",
                aggfunc="sum",
                fill_value=0,
            )
            .reset_index()
            .rename_axis(None, axis=1)
        )

    for column in required:
        if column not in frame.columns:
            frame[column] = 0
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    frame["three_party_net_shares"] = frame[required].sum(axis=1)

    market_map = _mapping_from_existing(existing_flow, column="market")
    name_map = _mapping_from_existing(existing_flow, column="stock_name")
    frame["market"] = _market_from_existing(frame, market_map)
    if "stock_name" not in frame.columns:
        frame["stock_name"] = frame["stock_code"].map(name_map).fillna("")
    else:
        frame["stock_name"] = frame["stock_name"].fillna(frame["stock_code"].map(name_map)).fillna("")

    output = pd.DataFrame(
        {
            "trade_date": frame["trade_date"],
            "market": frame["market"],
            "stock_code": frame["stock_code"],
            "stock_name": frame["stock_name"],
            "foreign_net_shares": frame["foreign_net_shares"],
            "dealer_net_shares": frame["dealer_net_shares"],
            "trustee_net_shares": frame["trustee_net_shares"],
            "three_party_net_shares": frame["three_party_net_shares"],
        }
    )
    return output


def _merge_and_write(existing: pd.DataFrame, incoming: pd.DataFrame, path: Path) -> int:
    if incoming.empty:
        if existing.empty and not path.exists():
            existing.to_parquet(path, index=False)
        return 0
    merged = pd.concat([existing, incoming], ignore_index=True, sort=False)
    merged["trade_date"] = _date_text(merged["trade_date"])
    merged["stock_code"] = _stock_code(merged["stock_code"])
    merged = merged.dropna(subset=["trade_date", "stock_code"])
    merged = merged.drop_duplicates(subset=["trade_date", "stock_code"], keep="last")
    merged = merged.sort_values(["trade_date", "stock_code"]).reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(path, index=False)
    return len(incoming)


def run_backfill() -> dict[str, Any]:
    finmind_price = _read_parquet(PROCESSED / "finmind_price.parquet")
    finmind_institutional = _read_parquet(PROCESSED / "finmind_institutional.parquet")
    existing_daily = _read_parquet(PROCESSED / "daily_price.parquet")
    existing_flow = _read_parquet(PROCESSED / "institutional_flow.parquet")

    price = _prepare_price(finmind_price, existing_daily)
    institutional = _prepare_institutional(finmind_institutional, existing_flow)

    price_rows = _merge_and_write(existing_daily, price, PROCESSED / "daily_price.parquet")
    institutional_rows = _merge_and_write(existing_flow, institutional, PROCESSED / "institutional_flow.parquet")

    return {
        "generated_at": _now_iso(),
        "price_rows_added": price_rows,
        "institutional_rows_added": institutional_rows,
    }


def main() -> None:
    summary = run_backfill()
    print(
        "Backfill complete: "
        f"price_rows_added={summary['price_rows_added']}, "
        f"institutional_rows_added={summary['institutional_rows_added']}"
    )


if __name__ == "__main__":
    main()
