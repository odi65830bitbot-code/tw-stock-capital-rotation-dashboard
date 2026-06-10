from __future__ import annotations

import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import data_quality


def test_recent_trading_day():
    df = pd.DataFrame({
        "trade_date": ["2026-06-05", "2026-06-06"],
        "stock_code": ["2330", "2337"],
    })
    result = data_quality.check_recent_trading_day(df, expected=pd.to_datetime("2026-06-06").date())
    assert result.status in {"pass", "warning"}


def test_stock_code_format():
    df = pd.DataFrame({
        "stock_code": ["2330", "1101", "ABC", "3231A"],
        "market": ["TWSE", "TWSE", "TWSE", "TWSE"],
    })
    result = data_quality.check_stock_code_format(df, "TWSE", "stock_code", label="twse")
    assert result.name == "stock_code_format"
    assert result.status in {"warning", "fail"}


def test_not_all_null():
    df = pd.DataFrame({"trade_volume": [None, None], "trade_value_twd": [None, None], "close": [100, 101]})
    result = data_quality.check_not_all_null(df, ["trade_volume", "trade_value_twd"], label="daily")
    assert result.status == "fail"


def test_run_data_quality_checks_aggregates_status():
    daily = pd.DataFrame({
        "trade_date": ["2026-06-06"],
        "market": ["TWSE"],
        "stock_code": ["2330"],
        "trade_volume": [1000.0],
        "trade_value_twd": [2000.0],
        "close": [50.0],
    })
    flow = pd.DataFrame({
        "trade_date": ["2026-06-06"],
        "market": ["TWSE"],
        "stock_code": ["2330"],
        "three_party_net_shares": [1234],
    })
    amount = pd.DataFrame({
        "trade_date": ["2026-06-06"],
        "purchase_amount_twd": [1_000_000],
        "sale_amount_twd": [900_000],
        "net_amount_twd": [100_000],
    })
    sector = pd.DataFrame({
        "stock_code": ["2330"],
        "industry": ["半導體"],
        "market": ["TWSE"],
    })
    report = data_quality.run_data_quality_checks(
        {
            "daily_price": daily,
            "institutional_flow": flow,
            "institutional_amount": amount,
            "sector_classification": sector,
        },
        expected_date=pd.to_datetime("2026-06-06").date(),
    )
    assert report["status"] in {"pass", "warning"}
    assert any(c["name"] == "reasonable_row_count" for c in report["checks"])
