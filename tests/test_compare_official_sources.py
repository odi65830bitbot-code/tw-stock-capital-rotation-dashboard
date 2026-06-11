from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts import compare_official_sources as compare


def test_compare_sector_rotation_matches_official_processed_data(tmp_path: Path):
    processed = tmp_path / "data" / "processed"
    public = tmp_path / "public" / "data"
    processed.mkdir(parents=True)
    public.mkdir(parents=True)

    pd.DataFrame(
        [
            {"trade_date": "2026-06-10", "market": "TWSE", "industry": "金融保險業", "three_party_net_shares": 3000, "stock_count": 2},
        ]
    ).to_parquet(processed / "sector_flow.parquet", index=False)
    pd.DataFrame(
        [
            {"trade_date": "2026-06-10", "market": "TWSE", "stock_code": "2892", "foreign_net_shares": 1000, "trustee_net_shares": 300, "dealer_net_shares": -100, "three_party_net_shares": 1200},
            {"trade_date": "2026-06-10", "market": "TWSE", "stock_code": "2887", "foreign_net_shares": 1500, "trustee_net_shares": 200, "dealer_net_shares": 100, "three_party_net_shares": 1800},
        ]
    ).to_parquet(processed / "institutional_flow.parquet", index=False)
    pd.DataFrame(
        [
            {"trade_date": "2026-06-10", "market": "TWSE", "stock_code": "2892", "close": 30.0, "change": 0.3, "trade_value_twd": 100_000_000},
            {"trade_date": "2026-06-10", "market": "TWSE", "stock_code": "2887", "close": 20.0, "change": -0.2, "trade_value_twd": 50_000_000},
        ]
    ).to_parquet(processed / "daily_price.parquet", index=False)
    pd.DataFrame(
        [
            {"as_of_date": "2026-06-10", "stock_code": "2892", "industry": "金融保險業", "market": "TWSE"},
            {"as_of_date": "2026-06-10", "stock_code": "2887", "industry": "金融保險業", "market": "TWSE"},
        ]
    ).to_parquet(processed / "sector_classification.parquet", index=False)
    pd.DataFrame(
        [
            {"trade_date": "2026-06-10", "market": "TWSE", "index_name": "TAIEX", "close": 100.0, "change": 1.0, "change_pct": 1.01},
        ]
    ).to_parquet(processed / "index.parquet", index=False)

    payload = {
        "status": "ok",
        "as_of_date": "2026-06-10",
        "records": [
            {
                "category": "TWSE",
                "sector_name": "銀行金融",
                "stock_count": 2,
                "net_1d_shares": 3000,
                "net_1d_yi": 0.0,
                "foreign_net_yi": 0.0,
                "trust_net_yi": 0.0,
                "dealer_net_yi": 0.0,
                "chg_1d": 0.0,
                "trade_value_yi": 1.5,
            }
        ],
    }
    expected = compare.build_expected_sector_records(processed)["TWSE|銀行金融"]
    payload["records"][0].update({field: expected[field] for field in ["net_1d_yi", "foreign_net_yi", "trust_net_yi", "dealer_net_yi", "chg_1d"]})
    (public / "sector_rotation_latest.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (public / "market_latest.json").write_text(
        json.dumps({"records": [{"index_name": "TAIEX", "close": 100.0, "change": 1.0, "change_pct": 1.01}]}),
        encoding="utf-8",
    )

    report = compare.build_report(public, processed)

    assert report["status"] == "ok"
    assert report["sector_rotation"]["mismatch_count"] == 0
    assert report["market"]["status"] == "ok"


def test_compare_sector_rotation_detects_mismatch(tmp_path: Path):
    processed = tmp_path / "data" / "processed"
    public = tmp_path / "public" / "data"
    processed.mkdir(parents=True)
    public.mkdir(parents=True)
    pd.DataFrame(
        [{"trade_date": "2026-06-10", "market": "TWSE", "industry": "金融保險業", "three_party_net_shares": 1000, "stock_count": 1}]
    ).to_parquet(processed / "sector_flow.parquet", index=False)
    pd.DataFrame(
        [{"trade_date": "2026-06-10", "market": "TWSE", "stock_code": "2892", "foreign_net_shares": 1000, "trustee_net_shares": 0, "dealer_net_shares": 0, "three_party_net_shares": 1000}]
    ).to_parquet(processed / "institutional_flow.parquet", index=False)
    pd.DataFrame(
        [{"trade_date": "2026-06-10", "market": "TWSE", "stock_code": "2892", "close": 30.0, "change": 0.3, "trade_value_twd": 100_000_000}]
    ).to_parquet(processed / "daily_price.parquet", index=False)
    pd.DataFrame(
        [{"as_of_date": "2026-06-10", "stock_code": "2892", "industry": "金融保險業", "market": "TWSE"}]
    ).to_parquet(processed / "sector_classification.parquet", index=False)
    pd.DataFrame().to_parquet(processed / "index.parquet", index=False)
    (public / "sector_rotation_latest.json").write_text(
        json.dumps({"records": [{"category": "TWSE", "sector_name": "銀行金融", "stock_count": 1, "net_1d_shares": 1000, "net_1d_yi": 999.0}]}),
        encoding="utf-8",
    )
    (public / "market_latest.json").write_text(json.dumps({"records": []}), encoding="utf-8")

    report = compare.build_report(public, processed)

    assert report["status"] == "mismatch"
    assert report["sector_rotation"]["mismatch_count"] == 1
