from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analysis.recommendations import build_recommendations, build_stock_alpha_breakdown


def _sample_stock_alpha() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "trade_date": "2026-06-05",
                "market": "TWSE",
                "stock_code": "3231",
                "stock_name": "緯創",
                "industry": "電腦及週邊設備業",
                "trade_volume": 10_000_000,
                "trade_value_twd": 1_500_000_000,
                "close": 100.0,
                "change": 4.0,
                "foreign_net_shares": 600_000,
                "dealer_net_shares": 20_000,
                "trustee_net_shares": 180_000,
                "three_party_net_shares": 800_000,
                "has_institutional_flow": True,
            },
            {
                "trade_date": "2026-06-05",
                "market": "TWSE",
                "stock_code": "2330",
                "stock_name": "台積電",
                "industry": "半導體業",
                "trade_volume": 50_000_000,
                "trade_value_twd": 50_000_000_000,
                "close": 1200.0,
                "change": 5.0,
                "foreign_net_shares": 100_000,
                "dealer_net_shares": 0,
                "trustee_net_shares": 10_000,
                "three_party_net_shares": 110_000,
                "has_institutional_flow": True,
            },
            {
                "trade_date": "2026-06-05",
                "market": "TWSE",
                "stock_code": "00632R",
                "stock_name": "元大台灣50反1",
                "industry": "UNKNOWN",
                "trade_volume": 80_000_000,
                "trade_value_twd": 500_000_000,
                "close": 3.0,
                "change": 0.2,
                "foreign_net_shares": 10_000_000,
                "dealer_net_shares": 0,
                "trustee_net_shares": 0,
                "three_party_net_shares": 10_000_000,
                "has_institutional_flow": True,
            },
            {
                "trade_date": "2026-06-05",
                "market": "TWSE",
                "stock_code": "9999",
                "stock_name": "低量股",
                "industry": "電腦及週邊設備業",
                "trade_volume": 10_000,
                "trade_value_twd": 300_000,
                "close": 30.0,
                "change": 0.1,
                "foreign_net_shares": 5_000,
                "dealer_net_shares": 0,
                "trustee_net_shares": 0,
                "three_party_net_shares": 5_000,
                "has_institutional_flow": True,
            },
        ]
    )


def _sample_sector_alpha() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "trade_date": "2026-06-05",
                "market": "TWSE",
                "industry": "電腦及週邊設備業",
                "sector_alpha_score": 80.0,
            },
            {
                "trade_date": "2026-06-05",
                "market": "TWSE",
                "industry": "半導體業",
                "sector_alpha_score": 40.0,
            },
        ]
    )


def _sample_sector_flow() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "trade_date": "2026-06-05",
                "market": "TWSE",
                "industry": "電腦及週邊設備業",
                "three_party_net_shares": 2_000_000,
                "stock_count": 20,
                "moneydj_flow_rate_accel_pct": 1.2,
                "moneydj_relative_strength_20d_pct": 3.4,
            },
            {
                "trade_date": "2026-06-05",
                "market": "TWSE",
                "industry": "半導體業",
                "three_party_net_shares": 500_000,
                "stock_count": 30,
                "moneydj_flow_rate_accel_pct": -0.2,
                "moneydj_relative_strength_20d_pct": 1.0,
            },
        ]
    )


def test_stock_alpha_breakdown_applies_weights_and_risk_filters():
    breakdown = build_stock_alpha_breakdown(
        _sample_stock_alpha(),
        _sample_sector_alpha(),
        _sample_sector_flow(),
    )

    wistron = breakdown[breakdown["stock_code"] == "3231"].iloc[0]
    assert wistron["alpha_score_total"] > 60
    assert wistron["sector_alpha_component"] >= 50
    assert wistron["main_buy_component"] >= 50
    assert wistron["risk_penalty"] == 0
    assert wistron["is_excluded"] is False

    inverse_etf = breakdown[breakdown["stock_code"] == "00632R"].iloc[0]
    assert inverse_etf["is_excluded"] is True
    assert "非普通股" in inverse_etf["exclusion_reason"]

    illiquid = breakdown[breakdown["stock_code"] == "9999"].iloc[0]
    assert illiquid["is_excluded"] is True
    assert "流動性不足" in illiquid["exclusion_reason"]


def test_recommendations_generate_neutral_reasons_and_candidates():
    recommendations, summary = build_recommendations(
        _sample_stock_alpha(),
        _sample_sector_alpha(),
        _sample_sector_flow(),
        per_sector=3,
        top_n=10,
    )

    assert not recommendations.empty
    assert "3231" in set(recommendations["stock_code"])
    assert "00632R" not in set(recommendations["stock_code"])
    assert "9999" not in set(recommendations["stock_code"])
    assert recommendations["suggested_status"].isin(["觀察", "分批觀察", "過熱", "避開"]).all()
    assert recommendations["summary"].str.len().min() > 0
    assert recommendations[["reason_1", "reason_2", "reason_3", "main_risk"]].notna().all().all()
    assert not summary.empty
    assert {"strongest_sector", "new_rotation_sector", "fading_sector"}.issubset(summary["summary_type"])
