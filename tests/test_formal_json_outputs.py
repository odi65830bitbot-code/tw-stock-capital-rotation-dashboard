from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import build_formal_json_outputs as formal


def test_compute_market_change_pct_prefers_market_latest(tmp_path, monkeypatch):
    public_data = tmp_path / "public" / "data"
    processed = tmp_path / "data" / "processed"
    public_data.mkdir(parents=True)
    processed.mkdir(parents=True)
    (public_data / "market_latest.json").write_text(
        json.dumps(
            {
                "records": [
                    {"index_name": "TPEX_INDEX", "close": 405.91, "change": -18.8},
                    {"index_name": "TAIEX", "close": 43225.54, "change": -1478.9},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(formal, "PUBLIC_DATA", public_data)
    monkeypatch.setattr(formal, "PROCESSED", processed)

    pct, is_down = formal.compute_market_change_pct()

    assert pct == -3.31
    assert is_down is True


def test_sector_records_include_institutional_split_and_concentration():
    sector_flow = pd.DataFrame(
        [
            {
                "trade_date": "2026-06-10",
                "market": "TWSE",
                "industry": "半導體業",
                "three_party_net_shares": 30_000_000,
                "stock_count": 2,
            }
        ]
    )
    institutional_flow = pd.DataFrame(
        [
            {
                "trade_date": "2026-06-10",
                "market": "TWSE",
                "stock_code": "2330",
                "foreign_net_shares": 10_000_000,
                "trustee_net_shares": 2_000_000,
                "dealer_net_shares": -1_000_000,
                "three_party_net_shares": 11_000_000,
            },
            {
                "trade_date": "2026-06-10",
                "market": "TWSE",
                "stock_code": "2454",
                "foreign_net_shares": 20_000_000,
                "trustee_net_shares": 3_000_000,
                "dealer_net_shares": -4_000_000,
                "three_party_net_shares": 19_000_000,
            },
            {
                "trade_date": "2026-06-09",
                "market": "TWSE",
                "stock_code": "2330",
                "foreign_net_shares": 1_000_000,
                "trustee_net_shares": 0,
                "dealer_net_shares": 0,
                "three_party_net_shares": 1_000_000,
            },
        ]
    )
    daily_price = pd.DataFrame(
        [
            {"trade_date": "2026-06-10", "market": "TWSE", "stock_code": "2330", "close": 100.0, "change": -1.0, "trade_volume": 100_000_000},
            {"trade_date": "2026-06-10", "market": "TWSE", "stock_code": "2454", "close": 200.0, "change": -2.0, "trade_volume": 200_000_000},
            {"trade_date": "2026-06-09", "market": "TWSE", "stock_code": "2330", "close": 50.0, "change": 5.0, "trade_volume": 90_000_000},
        ]
    )
    stock_alpha = pd.DataFrame(
        [
            {"stock_code": "2330", "industry": "半導體業", "market": "TWSE", "stock_name": "台積電"},
            {"stock_code": "2454", "industry": "半導體業", "market": "TWSE", "stock_name": "聯發科"},
        ]
    )

    records, _ = formal.build_official_sector_records(
        sector_flow,
        institutional_flow,
        daily_price,
        pd.DataFrame(),
        stock_alpha,
    )

    semi = records[0]
    assert semi["foreign_net_yi"] == 50.0
    assert semi["trust_net_yi"] == 8.0
    assert semi["dealer_net_yi"] == -9.0
    assert semi["concentration"] == 10.0
    assert semi["net_1d_yi"] == 49.0
    assert semi["net_5d_yi"] == 49.5


def test_recommendations_backtest_stats_fall_back_to_factor_effectiveness():
    records = [
        {"stock_code": "2330", "industry": "半導體", "model_win_rate": None, "model_max_drawdown": None, "backtest_status": "資料不足"},
        {"stock_code": "1101", "industry": "水泥", "model_win_rate": 0.62, "model_max_drawdown": -0.08, "backtest_status": "已回測"},
    ]
    stats = {"半導體": {"win_rate": 0.57, "max_drawdown": -0.12}}

    formal.fill_recommendation_backtest_stats(records, stats)

    assert records[0]["model_win_rate"] == 0.57
    assert records[0]["model_max_drawdown"] == -0.12
    assert records[0]["backtest_status"] == "產業統計估算"
    assert records[1]["model_win_rate"] == 0.62


def test_repair_existing_public_jsons_filters_codes_and_fills_fields(tmp_path, monkeypatch):
    public_data = tmp_path / "public" / "data"
    public_data.mkdir(parents=True)
    (public_data / "market_latest.json").write_text(
        json.dumps(
            {
                "records": [
                    {"index_name": "TAIEX", "close": 43225.54, "change": -1478.9, "change_pct": None},
                    {"index_name": "TPEx50Index", "close": None, "change": None, "change_pct": None},
                ]
            }
        ),
        encoding="utf-8",
    )
    (public_data / "sector_constituents_latest.json").write_text(
        json.dumps(
            {
                "records": [
                    {"stock_code": "006201"},
                    {
                        "stock_code": "2330",
                        "close": None,
                        "change_pct": None,
                        "foreign_net_shares": None,
                        "trustee_net_shares": None,
                        "dealer_net_shares": None,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (public_data / "recommendations_latest.json").write_text(
        json.dumps({"records": [{"stock_code": "2330", "industry": "半導體", "model_win_rate": None, "foreign_net_shares": None}]}),
        encoding="utf-8",
    )
    (public_data / "factor_effectiveness.json").write_text(
        json.dumps({"records": [{"factor": "alpha_score_total", "sector": "半導體", "win_rate": 0.58, "max_drawdown": -0.11}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(formal, "PUBLIC_DATA", public_data)

    changed = formal.repair_existing_public_jsons()

    market = json.loads((public_data / "market_latest.json").read_text(encoding="utf-8"))
    constituents = json.loads((public_data / "sector_constituents_latest.json").read_text(encoding="utf-8"))
    recommendations = json.loads((public_data / "recommendations_latest.json").read_text(encoding="utf-8"))
    assert changed == {
        "market_latest.json": 1,
        "sector_constituents_latest.json": 1,
        "recommendations_latest.json": 1,
    }
    assert market["records"][0]["change_pct"] == -3.31
    assert market["records"][1]["change_pct"] is None
    assert [r["stock_code"] for r in constituents["records"]] == ["2330"]
    assert constituents["records"][0]["close"] is None
    assert constituents["records"][0]["change_pct"] is None
    assert constituents["records"][0]["foreign_net_shares"] is None
    assert constituents["records"][0]["trustee_net_shares"] is None
    assert constituents["records"][0]["dealer_net_shares"] is None
    assert recommendations["records"][0]["model_win_rate"] == 0.58
    assert recommendations["records"][0]["foreign_net_shares"] is None
    assert "trustee_net_shares" not in recommendations["records"][0]
    assert "dealer_net_shares" not in recommendations["records"][0]
