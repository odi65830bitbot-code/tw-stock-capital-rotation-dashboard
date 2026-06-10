from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.alpha_v3 import compute_alpha_v3
from modules.factor_engine_finmind import compute_finmind_factors


def _price_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": f"2026-01-{day:02d}",
                "stock_id": "2330",
                "stock_name": "台積電",
                "close": 100 + day,
                "Trading_Volume": 1_000_000 + day,
                "Trading_money": 100_000_000 + day * 1_000_000,
            }
            for day in range(1, 31)
        ]
    )


def test_momentum_factors_are_calculated_from_history():
    factors = compute_finmind_factors(price=_price_rows())
    row = factors[factors["stock_id"] == "2330"].iloc[0]

    assert round(row["return_5d_raw"], 6) == round((130 / 125) - 1, 6)
    assert row["ma5_raw"] == 128
    assert row["ma20_raw"] == 120.5
    assert row["close_above_ma20_raw"] is True
    assert 0 <= row["return_5d"] <= 100
    assert 0 <= row["volatility_20d"] <= 100


def test_institutional_5d_and_20d_sums_are_calculated():
    institutional = pd.DataFrame(
        [
            {"date": f"2026-01-{day:02d}", "stock_id": "2330", "name": "Foreign_Investor", "buy": 100 + day, "sell": day}
            for day in range(1, 22)
        ]
        + [
            {"date": f"2026-01-{day:02d}", "stock_id": "2330", "name": "Investment_Trust", "buy": 50 + day, "sell": day}
            for day in range(1, 22)
        ]
    )

    factors = compute_finmind_factors(price=_price_rows(), institutional=institutional)
    row = factors[factors["stock_id"] == "2330"].iloc[0]

    assert row["foreign_buy_5d_raw"] == 500
    assert row["foreign_buy_20d_raw"] == 2000
    assert row["investment_trust_buy_5d_raw"] == 250
    assert row["institution_sync_score_raw"] > 0


def test_revenue_yoy_and_mom_are_calculated():
    revenue = pd.DataFrame(
        [
            {"date": "2025-05-10", "stock_id": "2330", "revenue": 1000},
            {"date": "2026-04-10", "stock_id": "2330", "revenue": 1200},
            {"date": "2026-05-10", "stock_id": "2330", "revenue": 1500},
        ]
    )

    factors = compute_finmind_factors(price=_price_rows(), revenue=revenue)
    row = factors[factors["stock_id"] == "2330"].iloc[0]

    assert round(row["revenue_yoy_raw"], 4) == 0.5
    assert round(row["revenue_mom_raw"], 4) == 0.25
    assert 0 <= row["revenue_acceleration_score"] <= 100


def test_alpha_score_and_risk_penalty_are_bounded():
    factors = compute_finmind_factors(price=_price_rows())
    alpha = compute_alpha_v3(factors)
    row = alpha.iloc[0]

    assert 0 <= row["stock_alpha_v3"] <= 100
    assert row["risk_penalty_total"] >= 0
