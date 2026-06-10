from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backtest.backtest import run_recommendation_backtests


def test_recommendation_backtest_uses_next_day_prices_only():
    prices = pd.DataFrame(
        [
            {"trade_date": "2026-01-02", "market": "TWSE", "stock_code": "1111", "stock_name": "甲股", "close": 100.0},
            {"trade_date": "2026-01-03", "market": "TWSE", "stock_code": "1111", "stock_name": "甲股", "close": 110.0},
            {"trade_date": "2026-01-02", "market": "TWSE", "stock_code": "2222", "stock_name": "乙股", "close": 100.0},
            {"trade_date": "2026-01-03", "market": "TWSE", "stock_code": "2222", "stock_name": "乙股", "close": 90.0},
            {"trade_date": "2026-01-02", "market": "TWSE", "stock_code": "0050", "stock_name": "元大台灣50", "close": 100.0},
            {"trade_date": "2026-01-03", "market": "TWSE", "stock_code": "0050", "stock_name": "元大台灣50", "close": 101.0},
        ]
    )
    scores = pd.DataFrame(
        [
            {"trade_date": "2026-01-02", "market": "TWSE", "stock_code": "1111", "alpha_score_total": 90.0},
            {"trade_date": "2026-01-02", "market": "TWSE", "stock_code": "2222", "alpha_score_total": 10.0},
        ]
    )
    index_df = pd.DataFrame(
        [
            {"trade_date": "2026-01-02", "market": "TWSE", "index_name": "發行量加權股價指數", "close": 100.0},
            {"trade_date": "2026-01-03", "market": "TWSE", "index_name": "發行量加權股價指數", "close": 102.0},
        ]
    )

    summary = run_recommendation_backtests(prices, scores, index_df, top_ns=(1,))

    row = summary.iloc[0]
    assert row["status"] == "ok"
    assert row["top_n"] == 1
    assert row["trading_days"] == 1
    assert round(row["cumulative_return"], 4) == 0.1
    assert round(row["benchmark_0050_return"], 4) == 0.01
    assert round(row["benchmark_taiex_return"], 4) == 0.02


def test_recommendation_backtest_reports_insufficient_history_for_single_day():
    prices = pd.DataFrame(
        [{"trade_date": "2026-01-02", "market": "TWSE", "stock_code": "1111", "stock_name": "甲股", "close": 100.0}]
    )
    scores = pd.DataFrame(
        [{"trade_date": "2026-01-02", "market": "TWSE", "stock_code": "1111", "alpha_score_total": 90.0}]
    )

    summary = run_recommendation_backtests(prices, scores, top_ns=(10, 20))

    assert summary["status"].tolist() == ["insufficient_history", "insufficient_history"]
    assert summary["top_n"].tolist() == [10, 20]
    assert summary["cumulative_return"].isna().all()
