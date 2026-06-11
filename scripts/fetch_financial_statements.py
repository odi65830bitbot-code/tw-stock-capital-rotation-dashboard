#!/usr/bin/env python3
"""Build latest fundamental flags for the v5 quant model.

The script prefers existing FinMind processed tables so it can run safely in
local/offline daily jobs. If a token is available, future extensions can add
live API refresh before this normalization step.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUTPUT = PROCESSED / "fundamentals_latest.parquet"

METRIC_ALIASES = {
    "eps": {"eps", "earningspershare", "basic_eps", "基本每股盈餘", "每股盈餘"},
    "net_income": {
        "incomeaftertaxes",
        "profitloss",
        "netincome",
        "netincomeaftertaxes",
        "本期淨利",
        "本期稅後淨利",
        "稅後淨利",
    },
    "contract_liability": {
        "contractliabilities",
        "currentcontractliabilities",
        "合約負債",
        "流動合約負債",
    },
    "revenue": {"revenue", "operatingrevenue", "營業收入", "收益"},
}


def _clean_metric(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def _metric_name(value: Any) -> str | None:
    cleaned = _clean_metric(value)
    for metric, aliases in METRIC_ALIASES.items():
        if cleaned in {_clean_metric(alias) for alias in aliases}:
            return metric
    return None


def _to_float(value: Any) -> float | None:
    try:
        num = float(str(value).replace(",", "").strip())
    except Exception:
        return None
    if math.isnan(num) or math.isinf(num):
        return None
    return num


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 2)


def _latest_previous(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series | None]:
    ordered = frame.sort_values("date")
    latest = ordered.iloc[-1]
    if len(ordered) == 1:
        return latest, None
    latest_date = pd.to_datetime(latest["date"])
    previous_candidates = ordered[pd.to_datetime(ordered["date"]) <= latest_date - pd.DateOffset(months=9)]
    if previous_candidates.empty:
        previous_candidates = ordered.iloc[:-1]
    return latest, previous_candidates.iloc[-1]


def build_fundamentals(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(
            columns=[
                "stock_code",
                "stock_id",
                "report_date",
                "eps",
                "net_income",
                "contract_liability",
                "revenue",
                "eps_yoy_pct",
                "net_income_yoy_pct",
                "contract_liability_revenue_ratio",
                "turnaround",
                "high_growth",
                "high_contract_liability",
            ]
        )

    required = {"date", "stock_id", "type", "value"}
    missing = required.difference(raw.columns)
    if missing:
        raise ValueError(f"financial raw data missing columns: {sorted(missing)}")

    work = raw.copy()
    work["metric"] = work["type"].map(_metric_name)
    work["value"] = work["value"].map(_to_float)
    work = work.dropna(subset=["metric", "value", "date", "stock_id"])
    if work.empty:
        return build_fundamentals(pd.DataFrame())

    pivot = (
        work.pivot_table(index=["stock_id", "date"], columns="metric", values="value", aggfunc="sum")
        .reset_index()
        .sort_values(["stock_id", "date"])
    )

    records: list[dict[str, Any]] = []
    for stock_id, stock_df in pivot.groupby("stock_id"):
        latest, previous = _latest_previous(stock_df)
        prev_eps = _to_float(previous.get("eps")) if previous is not None else None
        prev_income = _to_float(previous.get("net_income")) if previous is not None else None
        eps = _to_float(latest.get("eps"))
        net_income = _to_float(latest.get("net_income"))
        contract_liability = _to_float(latest.get("contract_liability"))
        revenue = _to_float(latest.get("revenue"))
        eps_yoy = _pct_change(eps, prev_eps)
        income_yoy = _pct_change(net_income, prev_income)
        ratio = (
            round(contract_liability / revenue, 4)
            if contract_liability is not None and revenue not in (None, 0)
            else None
        )
        turnaround = bool(
            (prev_eps is not None and eps is not None and prev_eps < 0 < eps)
            or (prev_income is not None and net_income is not None and prev_income < 0 < net_income)
        )
        high_growth = bool(turnaround or (eps_yoy is not None and eps_yoy >= 50) or (income_yoy is not None and income_yoy >= 50))
        high_contract = bool(ratio is not None and ratio >= 0.30)
        records.append(
            {
                "stock_code": str(stock_id),
                "stock_id": str(stock_id),
                "report_date": str(pd.to_datetime(latest["date"]).date()),
                "eps": eps,
                "net_income": net_income,
                "contract_liability": contract_liability,
                "revenue": revenue,
                "eps_yoy_pct": eps_yoy,
                "net_income_yoy_pct": income_yoy,
                "contract_liability_revenue_ratio": ratio,
                "turnaround": turnaround,
                "high_growth": high_growth,
                "high_contract_liability": high_contract,
            }
        )

    result = pd.DataFrame(records)
    for col in ["turnaround", "high_growth", "high_contract_liability"]:
        result[col] = result[col].map(lambda value: bool(value)).astype(object)
    return result.sort_values("stock_code").reset_index(drop=True)


def load_existing_financials() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    financial_path = PROCESSED / "finmind_financials.parquet"
    revenue_path = PROCESSED / "finmind_revenue.parquet"
    if financial_path.exists():
        frames.append(pd.read_parquet(financial_path)[["date", "stock_id", "type", "value"]])
    if revenue_path.exists():
        revenue = pd.read_parquet(revenue_path)
        if {"date", "stock_id", "revenue"}.issubset(revenue.columns):
            frames.append(
                revenue.assign(type="Revenue", value=revenue["revenue"])[["date", "stock_id", "type", "value"]]
            )
    if not frames:
        return pd.DataFrame(columns=["date", "stock_id", "type", "value"])
    return pd.concat(frames, ignore_index=True)


def main() -> int:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    raw = load_existing_financials()
    result = build_fundamentals(raw)
    result.to_parquet(OUTPUT, index=False)
    report = {
        "status": "ok" if not result.empty else "warning",
        "rows": int(len(result)),
        "source": "existing FinMind processed parquet",
        "token_available": bool(os.getenv("FINMIND_TOKEN")),
        "output": str(OUTPUT),
    }
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
