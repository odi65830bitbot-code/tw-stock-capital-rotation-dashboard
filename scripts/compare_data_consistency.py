from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.normalize_tpex import (
    normalize_tpex_daily_price,
    normalize_tpex_indices,
    normalize_tpex_institutional_amount,
    normalize_tpex_institutional_flow,
)
from src.data.normalize_twse import (
    normalize_twse_daily_price,
    normalize_twse_indices,
    normalize_twse_institutional_amount,
    normalize_twse_institutional_flow,
)
from src.data.tpex_client import _records_from_payload as tpex_records
from src.data.trading_calendar import latest_complete_trade_date
from src.data.twse_client import _records_from_payload as twse_records

TOLERANCE = 0.01


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _to_date_arg(value: str | None) -> date | None:
    if not value:
        return None
    if len(value) == 8 and value.isdigit():
        return date.fromisoformat(f"{value[:4]}-{value[4:6]}-{value[6:8]}")
    return date.fromisoformat(value)


def _load_raw_records(market: str, target: date, dataset: str) -> list[dict[str, Any]]:
    path = ROOT / "data" / "raw" / market / target.strftime("%Y%m%d") / f"{dataset}.json"
    if not path.exists():
        return []
    payload = _read_json(path)
    return twse_records(payload) if market == "twse" else tpex_records(payload)


def _raw_frames(target: date) -> dict[str, pd.DataFrame]:
    frames: dict[str, list[pd.DataFrame]] = {
        "daily_price": [],
        "institutional_flow": [],
        "institutional_amount": [],
        "index": [],
    }

    twse_daily = _load_raw_records("twse", target, "twse_daily_price")
    if twse_daily:
        frames["daily_price"].append(normalize_twse_daily_price(twse_daily))
    tpex_daily = _load_raw_records("tpex", target, "tpex_daily_price")
    if tpex_daily:
        frames["daily_price"].append(normalize_tpex_daily_price(tpex_daily))

    twse_flow = _load_raw_records("twse", target, "twse_institutional_flow")
    if twse_flow:
        frames["institutional_flow"].append(normalize_twse_institutional_flow(twse_flow))
    tpex_flow = _load_raw_records("tpex", target, "tpex_institutional_flow")
    if tpex_flow:
        frames["institutional_flow"].append(normalize_tpex_institutional_flow(tpex_flow))

    twse_amount = _load_raw_records("twse", target, "twse_institutional_amount")
    if twse_amount:
        frames["institutional_amount"].append(normalize_twse_institutional_amount(twse_amount))
    tpex_amount = _load_raw_records("tpex", target, "tpex_institutional_amount")
    if tpex_amount:
        frames["institutional_amount"].append(normalize_tpex_institutional_amount(tpex_amount))

    twse_index = _load_raw_records("twse", target, "twse_index")
    if twse_index:
        frames["index"].append(normalize_twse_indices(twse_index))
    tpex_index = _load_raw_records("tpex", target, "tpex_index")
    if tpex_index:
        frames["index"].append(normalize_tpex_indices(tpex_index))
    tpex_50 = _load_raw_records("tpex", target, "tpex_50_index")
    if tpex_50:
        frames["index"].append(normalize_tpex_indices(tpex_50).assign(index_name="TPEx50Index"))

    out = {
        name: pd.concat(items, ignore_index=True) if items else pd.DataFrame()
        for name, items in frames.items()
    }
    for df in out.values():
        if not df.empty and "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").fillna(pd.Timestamp(target))
            df.drop(df[df["trade_date"].dt.date != target].index, inplace=True)
    amount = out.get("institutional_amount", pd.DataFrame())
    if not amount.empty and "investor" in amount.columns:
        keep = amount["investor"].astype(str).isin(["合計", "三大法人合計", "三大法人合計*"])
        if keep.any():
            out["institutional_amount"] = amount[keep].copy()
    return out


def _processed_frame(name: str, target: date) -> pd.DataFrame:
    path = ROOT / "data" / "processed" / f"{name}.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    if "trade_date" in df.columns:
        df = df.copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        df = df[df["trade_date"].dt.date == target].copy()
    return df.reset_index(drop=True)


def _compare_frame(
    name: str,
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    keys: list[str],
    numeric_cols: list[str],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": name,
        "left_rows": int(len(left)),
        "right_rows": int(len(right)),
        "status": "pass",
        "messages": [],
    }
    if left.empty or right.empty:
        result["status"] = "warning"
        result["messages"].append("one side is empty")
        return result

    ldf = left.copy()
    rdf = right.copy()
    for df in (ldf, rdf):
        for key in keys:
            if key in df.columns:
                df[key] = df[key].astype(str)
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    key_cols = [key for key in keys if key in ldf.columns and key in rdf.columns]
    if len(key_cols) != len(keys):
        result["status"] = "fail"
        result["messages"].append(f"missing keys: expected {keys}, got {key_cols}")
        return result

    ldf = ldf.drop_duplicates(key_cols, keep="last")
    rdf = rdf.drop_duplicates(key_cols, keep="last")
    merged = ldf.merge(rdf, on=key_cols, how="outer", suffixes=("_left", "_right"), indicator=True)
    missing_left = int((merged["_merge"] == "right_only").sum())
    missing_right = int((merged["_merge"] == "left_only").sum())
    if missing_left or missing_right:
        result["status"] = "fail"
        result["messages"].append(f"key mismatch left_missing={missing_left} right_missing={missing_right}")

    mismatches: dict[str, int] = {}
    for col in numeric_cols:
        lcol = f"{col}_left"
        rcol = f"{col}_right"
        if lcol not in merged.columns or rcol not in merged.columns:
            continue
        lv = pd.to_numeric(merged[lcol], errors="coerce")
        rv = pd.to_numeric(merged[rcol], errors="coerce")
        diff = (lv - rv).abs()
        mismatch = int(((diff > TOLERANCE) & ~(lv.isna() & rv.isna())).sum())
        if mismatch:
            mismatches[col] = mismatch
    if mismatches:
        result["status"] = "fail"
        result["messages"].append(f"numeric mismatches: {mismatches}")
    return result


def _public_payload(name: str) -> tuple[str | None, pd.DataFrame]:
    path = ROOT / "public" / "data" / name
    if not path.exists():
        return None, pd.DataFrame()
    payload = _read_json(path)
    return payload.get("as_of_date"), pd.DataFrame(payload.get("records", []))


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    target = _to_date_arg(arg)
    if target is None:
        daily = pd.read_parquet(ROOT / "data" / "processed" / "daily_price.parquet")
        target = latest_complete_trade_date(daily).date()

    raw = _raw_frames(target)
    report: dict[str, Any] = {
        "target_date": target.isoformat(),
        "status": "pass",
        "checks": [],
    }

    specs = [
        ("raw_vs_processed_daily_price", raw["daily_price"], _processed_frame("daily_price", target), ["trade_date", "market", "stock_code"], ["open", "high", "low", "close", "change", "trade_volume", "trade_value_twd"]),
        ("raw_vs_processed_institutional_flow", raw["institutional_flow"], _processed_frame("institutional_flow", target), ["trade_date", "market", "stock_code"], ["foreign_net_shares", "dealer_net_shares", "trustee_net_shares", "three_party_net_shares"]),
        ("raw_vs_processed_institutional_amount", raw["institutional_amount"], _processed_frame("institutional_amount", target), ["trade_date", "market"], ["purchase_amount_twd", "sale_amount_twd", "net_amount_twd"]),
        ("raw_vs_processed_index", raw["index"], _processed_frame("index", target), ["trade_date", "market", "index_name"], ["open", "high", "low", "close", "change", "change_pct"]),
    ]
    for spec in specs:
        report["checks"].append(_compare_frame(*spec[:3], keys=spec[3], numeric_cols=spec[4]))

    public_specs = [
        ("public_market_latest", "market_latest.json", _processed_frame("index", target), ["trade_date", "market", "index_name"], ["open", "high", "low", "close", "change", "change_pct"]),
        ("public_sector_latest", "sector_latest.json", _processed_frame("sector_flow", target), ["trade_date", "market", "industry"], ["three_party_net_shares", "stock_count"]),
        ("public_stock_alpha_latest", "stock_alpha_latest.json", _processed_frame("stock_alpha_breakdown", target), ["trade_date", "market", "stock_code"], ["close", "trade_value_twd", "alpha_score_total", "main_buy_component", "foreign_component", "trust_component", "risk_penalty"]),
        ("public_recommendations_latest", "recommendations_latest.json", _processed_frame("recommendations", target), ["trade_date", "market", "stock_code"], ["close", "trade_value_twd", "alpha_score_total", "risk_penalty"]),
    ]
    for name, filename, processed, keys, cols in public_specs:
        as_of, public = _public_payload(filename)
        check = _compare_frame(name, public, processed, keys=keys, numeric_cols=cols)
        check["public_as_of_date"] = as_of
        if as_of != target.isoformat():
            check["status"] = "fail"
            check["messages"].append(f"public as_of_date mismatch: {as_of}")
        report["checks"].append(check)

    if any(check["status"] == "fail" for check in report["checks"]):
        report["status"] = "fail"
    elif any(check["status"] == "warning" for check in report["checks"]):
        report["status"] = "warning"

    out = ROOT / "reports" / f"data_consistency_{target:%Y%m%d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report={out}")
    raise SystemExit(0 if report["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
