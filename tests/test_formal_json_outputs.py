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


def test_sector_flow_history_aggregates_recent_sixty_trading_days():
    institutional_rows = []
    for day in pd.date_range("2026-03-01", periods=65, freq="D"):
        date = day.strftime("%Y-%m-%d")
        institutional_rows.extend(
            [
                {
                    "trade_date": date,
                    "stock_code": "2330",
                    "foreign_net_shares": 100,
                    "trustee_net_shares": 10,
                    "dealer_net_shares": -5,
                },
                {
                    "trade_date": date,
                    "stock_code": "2454",
                    "foreign_net_shares": 50,
                    "trustee_net_shares": 5,
                    "dealer_net_shares": 5,
                },
                {
                    "trade_date": date,
                    "stock_code": "2881",
                    "foreign_net_shares": -20,
                    "trustee_net_shares": 0,
                    "dealer_net_shares": 1,
                },
            ]
        )
    institutional_flow = pd.DataFrame(institutional_rows)
    sector_classification = pd.DataFrame(
        [
            {"as_of_date": "2026-06-01", "stock_code": "2330", "industry": "半導體業"},
            {"as_of_date": "2026-06-01", "stock_code": "2454", "industry": "半導體業"},
            {"as_of_date": "2026-06-01", "stock_code": "2881", "industry": "金融保險業"},
        ]
    )

    payload = formal.make_sector_flow_history_payload(institutional_flow, sector_classification)

    assert payload["status"] == "ok"
    assert payload["as_of_date"] == "2026-05-04"
    assert len(payload["dates"]) == 60
    assert payload["dates"][0] == "2026-03-06"
    assert payload["sectors"] == ["半導體業", "金融保險業"]
    latest_semi = next(row for row in payload["data"] if row["date"] == "2026-05-04" and row["sector"] == "半導體業")
    assert latest_semi == {
        "date": "2026-05-04",
        "sector": "半導體業",
        "foreign": 150,
        "trust": 15,
        "dealer": 0,
        "total": 165,
    }


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


def test_stock_alpha_payload_is_slimmed_for_dashboard_loading():
    records = [
        {
            "stock_code": f"{1000 + index}",
            "stock_id": f"{1000 + index}",
            "stock_name": f"股票{index}",
            "stock_alpha_v4": 100 - index,
        }
        for index in range(5)
    ]

    payload = formal.make_stock_alpha_payload(records, "2026-06-10", "stock_alpha_breakdown.parquet", limit=3)

    assert len(payload["records"]) == 3
    assert payload["total_records"] == 5
    assert payload["record_limit"] == 3
    assert payload["records_truncated"] is True
    assert payload["data_mode"] == "prepost_batch"
    assert payload["detail_template"] == "/data/trends/{stock_id}.json"


def test_data_manifest_marks_prepost_batch_and_file_sizes(tmp_path, monkeypatch):
    public_data = tmp_path / "public" / "data"
    public_data.mkdir(parents=True)
    (public_data / "stock_alpha_v4_latest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(formal, "PUBLIC_DATA", public_data)

    manifest = formal.make_data_manifest(
        {
            "stock_alpha_v4_latest.json": {
                "status": "ok",
                "data_timestamp": "2026-06-10",
                "records": 300,
                "total_records": 1200,
                "records_truncated": True,
            }
        }
    )

    assert manifest["data_mode"] == "prepost_batch"
    assert manifest["refresh_policy"] == "盤前/盤後批次更新；前端讀取靜態 JSON，不做即時輪詢。"
    assert manifest["files"]["stock_alpha_v4_latest.json"]["bytes"] == 2
    assert manifest["files"]["stock_alpha_v4_latest.json"]["records_truncated"] is True


def test_stock_lookup_payload_keeps_full_universe_basic_fields_only():
    daily_price = pd.DataFrame(
        [
            {
                "trade_date": "2026-06-09",
                "market": "TWSE",
                "stock_code": "2330",
                "stock_name": "台積電",
                "close": 100.0,
                "change": 1.0,
                "trade_value_twd": 1_000_000_000,
            },
            {
                "trade_date": "2026-06-10",
                "market": "TWSE",
                "stock_code": "2330",
                "stock_name": "台積電",
                "close": 110.0,
                "change": 5.0,
                "trade_value_twd": 2_000_000_000,
            },
            {
                "trade_date": "2026-06-10",
                "market": "TPEX",
                "stock_code": "3231",
                "stock_name": "緯創",
                "close": 88.0,
                "change": -2.0,
                "trade_value_twd": 500_000_000,
            },
            {
                "trade_date": "2026-06-10",
                "market": "TWSE",
                "stock_code": "00878",
                "stock_name": "國泰永續高股息",
                "close": 24.5,
                "change": 0.2,
                "trade_value_twd": 1_500_000_000,
            },
            {
                "trade_date": "2026-06-10",
                "market": "TWSE",
                "stock_code": "006208",
                "stock_name": "富邦台50",
                "close": 120.0,
                "change": 1.0,
                "trade_value_twd": 700_000_000,
            },
            {
                "trade_date": "2026-06-09",
                "market": "TPEX",
                "stock_code": "1591",
                "stock_name": "駿吉-KY",
                "close": 34.6,
                "change": -2.3,
                "trade_value_twd": 50_000_000,
            },
        ]
    )
    sector_classification = pd.DataFrame(
        [
            {"stock_code": "2330", "industry": "半導體業"},
            {"stock_code": "3231", "industry": "電腦及週邊設備業"},
            {"stock_code": "00878", "industry": "其他"},
            {"stock_code": "006208", "industry": "其他"},
            {"stock_code": "1591", "industry": "電機機械"},
        ]
    )

    payload = formal.make_stock_lookup_payload(daily_price, sector_classification)

    assert payload["status"] == "ok"
    assert payload["data_mode"] == "prepost_batch"
    assert payload["total_records"] == 5
    records = {record["stock_code"]: record for record in payload["records"]}
    assert records["2330"] == {
        "stock_code": "2330",
        "stock_id": "2330",
        "stock_name": "台積電",
        "market": "TWSE",
        "sector_name": "半導體",
        "industry": "半導體",
        "close": 110.0,
        "change": 5.0,
        "change_pct": 4.76,
        "trade_value_yi": 20.0,
        "price_date": "2026-06-10",
    }
    assert records["3231"]["sector_name"] == "電腦週邊"
    assert records["1591"]["stock_name"] == "駿吉-KY"
    assert records["1591"]["price_date"] == "2026-06-09"
    assert records["00878"]["sector_name"] == "ETF"
    assert records["006208"]["industry"] == "ETF"
    assert "alpha_score" not in records["2330"]


def test_stock_lookup_payload_uses_supplemental_industry_sources():
    daily_price = pd.DataFrame(
        [
            {
                "trade_date": "2026-06-12",
                "market": "TWSE",
                "stock_code": "3231",
                "stock_name": "緯創",
                "close": 156.0,
                "change": 3.5,
                "trade_value_twd": 5_948_000_000,
            }
        ]
    )
    supplemental = pd.DataFrame(
        [
            {
                "trade_date": "2026-06-12",
                "stock_code": "3231",
                "industry": "電腦及週邊設備業",
            }
        ]
    )

    payload = formal.make_stock_lookup_payload(daily_price, pd.DataFrame(), supplemental)

    assert payload["records"][0]["sector_name"] == "電腦週邊"
