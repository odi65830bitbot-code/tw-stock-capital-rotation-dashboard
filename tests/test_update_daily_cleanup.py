from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import update_daily


def test_clean_processed_frame_filters_daily_price_to_common_stocks():
    df = pd.DataFrame(
        [
            {"trade_date": "2026-06-10", "market": "TWSE", "stock_code": "2330", "close": 100},
            {"trade_date": "2026-06-10", "market": "TPEX", "stock_code": "006201", "close": 45},
            {"trade_date": "2026-06-10", "market": "TWSE", "stock_code": "700001", "close": None},
        ]
    )

    cleaned = update_daily._clean_processed_frame("daily_price", df)

    assert cleaned["stock_code"].tolist() == ["2330"]


def test_merge_frame_drops_nat_trade_dates_and_preserves_history():
    existing = pd.DataFrame(
        [
            {"trade_date": "2026-06-09", "market": "TWSE", "stock_code": "2330", "close": 100},
        ]
    )
    incoming = pd.DataFrame(
        [
            {"trade_date": "2026-06-10", "market": "TWSE", "stock_code": "2330", "close": 101},
            {"trade_date": None, "market": "TWSE", "stock_code": "2454", "close": 800},
        ]
    )

    merged = update_daily._merge_frame(
        existing,
        incoming,
        ["trade_date", "market", "stock_code"],
        dataset_name="institutional_flow",
    )

    assert merged["trade_date"].isna().sum() == 0
    assert merged["trade_date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-06-09", "2026-06-10"]
