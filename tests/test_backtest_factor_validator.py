from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.backtest_factor_validator import run_alpha_v3_backtest, validate_factor_effectiveness


def test_factor_ic_and_rank_ic_can_be_calculated_without_future_data():
    factors = pd.DataFrame(
        [
            {"trade_date": "2026-01-02", "stock_id": "1111", "stock_alpha_v3": 90, "return_20d": 80},
            {"trade_date": "2026-01-02", "stock_id": "2222", "stock_alpha_v3": 10, "return_20d": 20},
        ]
    )
    prices = pd.DataFrame(
        [
            {"date": "2026-01-02", "stock_id": "1111", "close": 100},
            {"date": "2026-01-03", "stock_id": "1111", "close": 110},
            {"date": "2026-01-02", "stock_id": "2222", "close": 100},
            {"date": "2026-01-03", "stock_id": "2222", "close": 90},
        ]
    )

    out = validate_factor_effectiveness(factors, prices, factor_cols=["stock_alpha_v3", "return_20d"])

    assert not out.empty
    assert set(out["factor"]) == {"stock_alpha_v3", "return_20d"}
    assert out["ic"].notna().all()
    assert out["uses_future_data"].eq(False).all()


def test_top_10_backtest_outputs_next_day_return_with_costs():
    alpha = pd.DataFrame(
        [
            {"trade_date": "2026-01-02", "market": "TWSE", "stock_id": "1111", "stock_alpha_v3": 90},
            {"trade_date": "2026-01-02", "market": "TWSE", "stock_id": "2222", "stock_alpha_v3": 10},
        ]
    )
    prices = pd.DataFrame(
        [
            {"date": "2026-01-02", "market": "TWSE", "stock_id": "1111", "close": 100},
            {"date": "2026-01-03", "market": "TWSE", "stock_id": "1111", "close": 110},
            {"date": "2026-01-02", "market": "TWSE", "stock_id": "2222", "close": 100},
            {"date": "2026-01-03", "market": "TWSE", "stock_id": "2222", "close": 90},
        ]
    )

    summary = run_alpha_v3_backtest(prices, alpha, top_ns=(1, 10), slippage=0)

    assert summary[summary["top_n"] == 1].iloc[0]["status"] == "ok"
    assert summary[summary["top_n"] == 10].iloc[0]["status"] == "ok"
    assert summary[summary["top_n"] == 1].iloc[0]["cumulative_return"] < 0.1
