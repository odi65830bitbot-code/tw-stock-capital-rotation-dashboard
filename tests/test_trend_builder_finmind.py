from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.trend_builder_finmind import DEFAULT_TREND_TOP_N, write_finmind_recommendation_trends


def test_default_finmind_trend_top_n_is_dashboard_sized():
    assert DEFAULT_TREND_TOP_N == 100


def test_write_finmind_recommendation_trends_defaults_to_price_universe(tmp_path):
    processed = tmp_path / "processed"
    public = tmp_path / "public"
    processed.mkdir()
    price = pd.DataFrame(
        [
            {
                "date": "2026-06-10",
                "stock_id": stock_id,
                "stock_name": stock_name,
                "close": close,
                "Trading_money": close * 1000,
            }
            for stock_id, stock_name, close in [
                ("2330", "台積電", 1000.0),
                ("8358", "金居", 555.0),
                ("1227", "佳格", 28.35),
            ]
        ]
    )
    recommendations = pd.DataFrame(
        [
            {
                "trade_date": "2026-06-10",
                "stock_id": "2330",
                "stock_name": "台積電",
                "market": "TWSE",
                "sector": "半導體業",
                "recommendation_type": "observe",
                "status": "ok",
                "summary_reason": "sample",
                "stock_alpha_v3": 90.0,
            }
        ]
    )

    price.to_parquet(processed / "finmind_price.parquet", index=False)
    pd.DataFrame().to_parquet(processed / "finmind_institutional.parquet", index=False)
    pd.DataFrame().to_parquet(processed / "finmind_margin.parquet", index=False)
    pd.DataFrame().to_parquet(processed / "finmind_revenue.parquet", index=False)
    pd.DataFrame().to_parquet(processed / "stock_alpha_v3.parquet", index=False)
    recommendations.to_parquet(processed / "recommendations_v3.parquet", index=False)

    paths = write_finmind_recommendation_trends(processed_root=processed, public_root=public)

    assert len(paths) == 3
    assert (public / "data" / "trends" / "8358.json").exists()
