from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import build_formal_json_outputs as formal
from scripts import fetch_financial_statements as financials
from scripts import fetch_sentiment_and_macro as sentiment


def test_build_fundamentals_flags_turnaround_growth_and_contract_liability():
    raw = pd.DataFrame(
        [
            {"date": "2025-03-31", "stock_id": "1234", "type": "EPS", "value": -0.5},
            {"date": "2026-03-31", "stock_id": "1234", "type": "EPS", "value": 1.2},
            {"date": "2025-03-31", "stock_id": "1234", "type": "IncomeAfterTaxes", "value": -100.0},
            {"date": "2026-03-31", "stock_id": "1234", "type": "IncomeAfterTaxes", "value": 240.0},
            {"date": "2026-03-31", "stock_id": "1234", "type": "ContractLiabilities", "value": 1800.0},
            {"date": "2026-03-31", "stock_id": "1234", "type": "Revenue", "value": 3000.0},
        ]
    )

    result = financials.build_fundamentals(raw)

    row = result.iloc[0].to_dict()
    assert row["stock_code"] == "1234"
    assert row["turnaround"] is True
    assert row["high_growth"] is True
    assert row["high_contract_liability"] is True
    assert row["eps_yoy_pct"] == 340.0


def test_build_sentiment_counts_stock_mentions_and_temperature():
    news = [
        {"title": "台積電 2330 AI 訂單強勁 營收成長創高"},
        {"title": "台積電 2330 外資看好 但短線過熱"},
        {"title": "鴻海 2317 需求疲弱 下修展望"},
    ]
    universe = pd.DataFrame(
        [
            {"stock_code": "2330", "stock_name": "台積電"},
            {"stock_code": "2317", "stock_name": "鴻海"},
        ]
    )

    result = sentiment.build_sentiment_records(news, universe)

    tsmc = result[result["stock_code"] == "2330"].iloc[0].to_dict()
    assert tsmc["mention_count"] == 2
    assert tsmc["sentiment_score"] > 0
    assert tsmc["sentiment_temperature"] >= 70


def test_build_sentiment_returns_schema_when_news_mentions_no_stock():
    news = [{"title": "美股指數震盪 市場等待利率決策"}]
    universe = pd.DataFrame([{"stock_code": "2330", "stock_name": "台積電"}])

    result = sentiment.build_sentiment_records(news, universe)

    assert result.empty
    assert {"stock_code", "sentiment_temperature", "mention_count"}.issubset(result.columns)


def test_make_quant_recommendations_applies_liquidity_sector_cap_and_tags(tmp_path, monkeypatch):
    processed = tmp_path / "data" / "processed"
    public_data = tmp_path / "public" / "data"
    processed.mkdir(parents=True)
    public_data.mkdir(parents=True)
    monkeypatch.setattr(formal, "PROCESSED", processed)
    monkeypatch.setattr(formal, "PUBLIC_DATA", public_data)

    dates = pd.date_range("2026-05-01", periods=22, freq="B")
    price_rows = []
    for code, volume in {
        "1001": 1_500_000,
        "1002": 1_600_000,
        "1003": 1_700_000,
        "1004": 1_800_000,
        "2001": 900_000,
    }.items():
        for idx, date in enumerate(dates):
            price_rows.append(
                {
                    "trade_date": date,
                    "market": "TWSE",
                    "stock_code": code,
                    "stock_name": f"股票{code}",
                    "close": 40 + idx,
                    "change": 1.0 if idx == len(dates) - 1 else 0.2,
                    "trade_volume": volume,
                    "trade_value_twd": volume * (40 + idx),
                }
            )
    pd.DataFrame(price_rows).to_parquet(processed / "daily_price.parquet")

    stock_records = []
    for index, code in enumerate(["1001", "1002", "1003", "1004", "2001"], start=1):
        stock_records.append(
            {
                "stock_code": code,
                "stock_id": code,
                "stock_name": f"股票{code}",
                "market": "TWSE",
                "sector_name": "半導體" if code.startswith("100") else "觀光餐旅",
                "industry": "半導體" if code.startswith("100") else "觀光餐旅",
                "stock_alpha_v4": 80 - index,
                "alpha_score": 80 - index,
                "three_party_net_shares": 120_000 * index,
                "net_1d_yi": 0.4 * index,
                "reason": "法人買超",
                "suggested_status": "觀察",
            }
        )

    fundamentals = pd.DataFrame(
        [
            {
                "stock_code": "1001",
                "turnaround": True,
                "high_growth": True,
                "high_contract_liability": False,
                "eps_yoy_pct": 220.0,
            }
        ]
    )
    sentiment_df = pd.DataFrame(
        [
            {
                "stock_code": "1001",
                "sentiment_score": 0.8,
                "sentiment_temperature": 88.0,
                "mention_count": 5,
            }
        ]
    )

    payload = formal.make_quant_recommendations_payload(stock_records, "2026-06-10", fundamentals, sentiment_df)

    records = payload["records"]
    assert payload["version"] == "recommendations-v5-quant-sentiment-v1"
    assert "2001" not in [row["stock_code"] for row in records]
    assert sum(1 for row in records if row["sector_name"] == "半導體") == 3
    assert records[0]["Alpha_Score_v5"] > records[-1]["Alpha_Score_v5"]
    assert "由虧轉盈" in records[0]["tags"]
    assert records[0]["sentiment_temperature"] == 88.0
