from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd


def test_backfill_merges_finmind_history_and_computes_three_party_flow(tmp_path, monkeypatch):
    backfill = importlib.import_module("scripts.backfill_from_finmind")
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    monkeypatch.setattr(backfill, "PROCESSED", processed)

    pd.DataFrame(
        [
            {
                "date": "2026-06-09",
                "stock_id": "2330",
                "open": 100.0,
                "max": 104.0,
                "min": 99.0,
                "close": 103.0,
                "spread": 3.0,
                "Trading_Volume": 1000,
                "Trading_money": 103000,
            },
            {
                "date": "2026-06-09",
                "stock_id": "0050",
                "close": 180.0,
                "spread": 1.0,
            },
            {
                "date": "2026-06-09",
                "stock_id": "1227",
                "close": 28.35,
                "spread": -0.1,
            },
        ]
    ).to_parquet(processed / "finmind_price.parquet", index=False)
    pd.DataFrame(
        [
            {"date": "2026-06-09", "stock_id": "2330", "name": "Foreign_Investor", "buy": 500, "sell": 100},
            {"date": "2026-06-09", "stock_id": "2330", "name": "Investment_Trust", "buy": 120, "sell": 20},
            {"date": "2026-06-09", "stock_id": "2330", "name": "Dealer_self", "buy": 40, "sell": 70},
        ]
    ).to_parquet(processed / "finmind_institutional.parquet", index=False)
    pd.DataFrame(
        [
            {
                "trade_date": "2026-06-09",
                "market": "TWSE",
                "stock_code": "2330",
                "stock_name": "台積電",
                "close": 101.0,
                "change": 1.0,
            },
            {
                "trade_date": "2026-06-08",
                "market": "TWSE",
                "stock_code": "2330",
                "stock_name": "台積電",
                "close": 100.0,
                "change": 0.5,
            },
        ]
    ).to_parquet(processed / "daily_price.parquet", index=False)
    pd.DataFrame(
        [
            {
                "trade_date": "2026-06-08",
                "market": "TWSE",
                "stock_code": "2330",
                "stock_name": "台積電",
                "foreign_net_shares": 1,
                "trustee_net_shares": 2,
                "dealer_net_shares": 3,
                "three_party_net_shares": 6,
            }
        ]
    ).to_parquet(processed / "institutional_flow.parquet", index=False)

    summary = backfill.run_backfill()

    daily = pd.read_parquet(processed / "daily_price.parquet")
    flow = pd.read_parquet(processed / "institutional_flow.parquet")

    latest_price = daily[(daily["trade_date"] == "2026-06-09") & (daily["stock_code"] == "2330")].iloc[0]
    unmapped_price = daily[(daily["trade_date"] == "2026-06-09") & (daily["stock_code"] == "1227")].iloc[0]
    latest_flow = flow[(flow["trade_date"] == "2026-06-09") & (flow["stock_code"] == "2330")].iloc[0]
    assert summary["price_rows_added"] == 2
    assert summary["institutional_rows_added"] == 1
    assert daily["stock_code"].tolist().count("0050") == 0
    assert latest_price["close"] == 103.0
    assert latest_price["change"] == 3.0
    assert latest_price["market"] == "TWSE"
    assert unmapped_price["market"] == "UNKNOWN"
    assert latest_flow["foreign_net_shares"] == 400
    assert latest_flow["trustee_net_shares"] == 100
    assert latest_flow["dealer_net_shares"] == -30
    assert latest_flow["three_party_net_shares"] == 470
