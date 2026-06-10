from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.modules.trend_builder import build_stock_trend, top_recommendation_codes


def test_top_recommendation_codes_limits_to_top_10_overall():
    recs = pd.DataFrame(
        [
            {
                "trade_date": "2026-06-05",
                "stock_code": f"{1000 + i}",
                "overall_rank": i,
                "alpha_score_total": 100 - i,
                "is_top_overall": i <= 10,
            }
            for i in range(1, 16)
        ]
    )

    codes = top_recommendation_codes(recs, top_n=10)

    assert len(codes) == 10
    assert codes[0] == "1001"
    assert codes[-1] == "1010"


def test_build_stock_trend_calculates_basic_series_and_recommend_performance():
    daily = pd.DataFrame(
        [
            {"trade_date": "2026-06-01", "market": "TWSE", "stock_code": "2330", "stock_name": "台積電", "close": 100.0, "trade_value_twd": 1000.0},
            {"trade_date": "2026-06-02", "market": "TWSE", "stock_code": "2330", "stock_name": "台積電", "close": 110.0, "trade_value_twd": 2000.0},
        ]
    )
    flow = pd.DataFrame(
        [
            {"trade_date": "2026-06-01", "market": "TWSE", "stock_code": "2330", "foreign_net_shares": 10, "trustee_net_shares": 5, "dealer_net_shares": 1},
            {"trade_date": "2026-06-02", "market": "TWSE", "stock_code": "2330", "foreign_net_shares": 20, "trustee_net_shares": 8, "dealer_net_shares": 2},
        ]
    )
    alpha = pd.DataFrame(
        [
            {"trade_date": "2026-06-01", "market": "TWSE", "stock_code": "2330", "industry": "半導體業", "stock_alpha_score": 1.0, "alpha_score_total": 60.0, "main_buy_component": 50.0, "risk_penalty": 0.0},
            {"trade_date": "2026-06-02", "market": "TWSE", "stock_code": "2330", "industry": "半導體業", "stock_alpha_score": 2.0, "alpha_score_total": 70.0, "main_buy_component": 60.0, "risk_penalty": 0.0},
        ]
    )
    sector_alpha = pd.DataFrame(
        [
            {"trade_date": "2026-06-01", "market": "TWSE", "industry": "半導體業", "sector_alpha_score": 50.0},
            {"trade_date": "2026-06-02", "market": "TWSE", "industry": "半導體業", "sector_alpha_score": 55.0},
        ]
    )
    recs = pd.DataFrame(
        [{"trade_date": "2026-06-01", "market": "TWSE", "stock_code": "2330", "alpha_score_total": 60.0}]
    )

    payload = build_stock_trend("2330", daily, flow, alpha, sector_alpha, recs)

    assert payload["stock_id"] == "2330"
    assert len(payload["price"]) == 2
    assert payload["price"][-1]["ma5"] == 105.0
    assert round(payload["recommendation"]["post_recommend_return"], 4) == 0.1
