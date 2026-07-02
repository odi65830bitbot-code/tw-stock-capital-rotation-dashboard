from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import build_formal_json_outputs as formal


def test_bdd_etf_lookup_keeps_price_identity_and_etf_classification():
    # Given an ETF appears in official daily prices and sector data only says "其他".
    daily_price = pd.DataFrame(
        [
            {
                "trade_date": "2026-06-12",
                "market": "TWSE",
                "stock_code": "00878",
                "stock_name": "國泰永續高股息",
                "close": 32.05,
                "change": 0.45,
                "trade_value_twd": 1_690_000_000,
            }
        ]
    )
    sector_classification = pd.DataFrame([{"stock_code": "00878", "industry": "其他"}])

    # When the dashboard lookup dictionary is generated.
    payload = formal.make_stock_lookup_payload(daily_price, sector_classification)

    # Then the ETF is searchable with basic price fields and is not hidden under "其他".
    assert payload["status"] == "ok"
    assert payload["scope"] == "common_stock_and_etf_basic_fields"
    assert payload["records"] == [
        {
            "stock_code": "00878",
            "stock_id": "00878",
            "stock_name": "國泰永續高股息",
            "market": "TWSE",
            "sector_name": "ETF",
            "industry": "ETF",
            "close": 32.05,
            "change": 0.45,
            "change_pct": 1.42,
            "trade_value_yi": 16.9,
            "price_date": "2026-06-12",
        }
    ]


def test_bdd_etf_holdings_payload_exposes_constituents_and_weights():
    # Given an ETF holdings dataset with constituent stock weights.
    holdings = pd.DataFrame(
        [
            {
                "as_of_date": "2026-06-12",
                "etf_code": "00878",
                "etf_name": "國泰永續高股息",
                "constituent_code": "2382",
                "constituent_name": "廣達",
                "weight_pct": 10.51,
                "shares": 168_840_000,
                "market_value_twd": 63_320_000_000,
                "source": "official_or_issuer_file",
            },
            {
                "as_of_date": "2026-06-12",
                "etf_code": "00878",
                "etf_name": "國泰永續高股息",
                "constituent_code": "2891",
                "constituent_name": "中信金",
                "weight_pct": 10.17,
                "shares": 885_740_000,
                "market_value_twd": 61_290_000_000,
                "source": "official_or_issuer_file",
            },
        ]
    )

    # When the ETF holdings public JSON is generated.
    payload = formal.make_etf_holdings_payload(holdings)

    # Then the ETF has an updateable constituent list with weights and coverage.
    assert payload["status"] == "ok"
    assert payload["data_timestamp"] == "2026-06-12"
    assert payload["total_etfs"] == 1
    assert payload["total_records"] == 2
    assert payload["records"][0]["etf_code"] == "00878"
    assert payload["records"][0]["holdings_count"] == 2
    assert payload["records"][0]["weight_coverage_pct"] == 20.68
    assert payload["records"][0]["constituents"][0] == {
        "stock_code": "2382",
        "stock_id": "2382",
        "stock_name": "廣達",
        "weight_pct": 10.51,
        "shares": 168840000.0,
        "market_value_yi": 633.2,
    }
