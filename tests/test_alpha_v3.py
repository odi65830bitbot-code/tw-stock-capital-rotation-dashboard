from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.alpha_v3 import compute_alpha_v3


def test_alpha_v3_weights_match_spec_when_all_components_are_present():
    factors = pd.DataFrame(
        [
            {
                "stock_id": "2330",
                "stock_name": "台積電",
                "sector_alpha": 80,
                "foreign_buy_5d": 70,
                "foreign_buy_20d": 90,
                "investment_trust_buy_5d": 60,
                "investment_trust_buy_20d": 80,
                "trade_value_ratio_20d": 50,
                "return_20d": 40,
                "return_60d": 60,
                "revenue_acceleration_score": 70,
                "quality_score": 80,
                "valuation_score": 90,
                "credit_health_score": 55,
                "main_force_proxy": 65,
                "risk_penalty_total": 0,
            }
        ]
    )

    out = compute_alpha_v3(factors)
    row = out.iloc[0]
    expected = (
        80 * 0.15
        + 80 * 0.15
        + 70 * 0.15
        + 50 * 0.10
        + 50 * 0.10
        + 70 * 0.10
        + 80 * 0.08
        + 90 * 0.07
        + 55 * 0.05
        + 65 * 0.05
    )

    assert round(row["stock_alpha_v3"], 4) == round(expected, 4)
    assert row["alpha_breakdown"]["foreign_score"] == 80
    assert "法人同步" in row["alpha_reason_codes"]


def test_confidence_score_drops_when_data_is_missing():
    full = compute_alpha_v3(
        pd.DataFrame(
            [
                {
                    "stock_id": "2330",
                    "sector_alpha": 80,
                    "foreign_buy_5d": 70,
                    "foreign_buy_20d": 70,
                    "investment_trust_buy_5d": 70,
                    "investment_trust_buy_20d": 70,
                    "liquidity_score": 90,
                    "institution_sync_score": 80,
                    "risk_penalty_total": 0,
                }
            ]
        )
    )
    sparse = compute_alpha_v3(pd.DataFrame([{"stock_id": "2330", "sector_alpha": 80}]))

    assert sparse.iloc[0]["confidence_score"] < full.iloc[0]["confidence_score"]


def test_high_volatility_and_overheat_reduce_alpha():
    base = {
        "stock_id": "2330",
        "sector_alpha": 90,
        "foreign_buy_5d": 90,
        "foreign_buy_20d": 90,
        "investment_trust_buy_5d": 90,
        "investment_trust_buy_20d": 90,
        "trade_value_ratio_20d": 90,
        "return_20d": 90,
        "return_60d": 90,
        "revenue_acceleration_score": 90,
        "quality_score": 90,
        "valuation_score": 90,
        "credit_health_score": 90,
        "main_force_proxy": 90,
    }
    normal = compute_alpha_v3(pd.DataFrame([{**base, "risk_penalty_total": 0}]))
    risky = compute_alpha_v3(
        pd.DataFrame([{**base, "overheat_penalty": 15, "high_volatility_penalty": 20, "risk_penalty_total": 35}])
    )

    assert risky.iloc[0]["stock_alpha_v3"] < normal.iloc[0]["stock_alpha_v3"]
    assert "高波動" in risky.iloc[0]["risk_tags"]
