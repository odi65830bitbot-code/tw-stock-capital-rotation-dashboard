from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.modules.trend_builder import DEFAULT_TREND_TOP_N, build_stock_trend, top_recommendation_codes, write_top_recommendation_trends


def test_default_trend_top_n_is_dashboard_sized():
    assert DEFAULT_TREND_TOP_N == 100


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


def test_write_top_recommendation_trends_defaults_to_latest_price_universe(tmp_path):
    processed = tmp_path / "processed"
    public = tmp_path / "public"
    processed.mkdir()
    latest_rows = [
        {
            "trade_date": "2026-06-10",
            "market": "TWSE",
            "stock_code": f"{1000 + i}",
            "stock_name": f"股票{i}",
            "close": float(100 + i),
            "trade_value_twd": float(1000 + i),
        }
        for i in range(1, 13)
    ]
    daily = pd.DataFrame(
        [
            {
                "trade_date": "2026-06-09",
                "market": "TWSE",
                "stock_code": "9999",
                "stock_name": "舊資料",
                "close": 99.0,
                "trade_value_twd": 999.0,
            },
            *latest_rows,
        ]
    )
    recommendations = pd.DataFrame(
        [
            {
                "trade_date": "2026-06-10",
                "stock_code": f"{1000 + i}",
                "overall_rank": i,
                "alpha_score_total": 100 - i,
                "is_top_overall": i <= 10,
            }
            for i in range(1, 13)
        ]
    )

    daily.to_parquet(processed / "daily_price.parquet", index=False)
    pd.DataFrame().to_parquet(processed / "institutional_flow.parquet", index=False)
    pd.DataFrame().to_parquet(processed / "stock_alpha_breakdown.parquet", index=False)
    pd.DataFrame().to_parquet(processed / "sector_alpha.parquet", index=False)
    recommendations.to_parquet(processed / "recommendations.parquet", index=False)

    paths = write_top_recommendation_trends(processed_root=processed, public_root=public)

    assert len(paths) == 12
    assert (public / "data" / "trends" / "1012.json").exists()
    assert not (public / "data" / "trends" / "9999.json").exists()


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
