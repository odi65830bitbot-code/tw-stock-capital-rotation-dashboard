from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import update_daily


def test_clean_processed_frame_keeps_common_stocks_and_etfs():
    df = pd.DataFrame(
        [
            {"trade_date": "2026-06-10", "market": "TWSE", "stock_code": "2330", "close": 100},
            {"trade_date": "2026-06-10", "market": "TPEX", "stock_code": "006201", "close": 45},
            {"trade_date": "2026-06-10", "market": "TWSE", "stock_code": "00878", "close": 24.5},
            {"trade_date": "2026-06-10", "market": "TWSE", "stock_code": "00400A", "close": 10.25},
            {"trade_date": "2026-06-10", "market": "TWSE", "stock_code": "700001", "close": None},
        ]
    )

    cleaned = update_daily._clean_processed_frame("daily_price", df)

    assert cleaned["stock_code"].tolist() == ["2330", "006201", "00878", "00400A"]


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
        dataset_name="sector_flow",
    )

    assert merged["trade_date"].isna().sum() == 0
    assert merged["trade_date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-06-09", "2026-06-10"]


def test_cap_sector_constituents_keeps_top_rows_per_market_sector():
    rows = []
    for sector in ["半導體業", "金融保險業"]:
        for index in range(5):
            rows.append(
                {
                    "market": "TWSE",
                    "industry": sector,
                    "stock_code": f"{2300 + index}",
                    "three_party_net_shares": 5 - index,
                    "trade_value_twd": 1000 + index,
                }
            )
    df = pd.DataFrame(rows)

    capped = update_daily._cap_sector_constituents(df, per_group=2)

    assert len(capped) == 4
    assert capped.groupby(["market", "industry"]).size().to_dict() == {
        ("TWSE", "半導體業"): 2,
        ("TWSE", "金融保險業"): 2,
    }
    assert capped[capped["industry"] == "半導體業"]["three_party_net_shares"].tolist() == [5, 4]
