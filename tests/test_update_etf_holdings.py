from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import update_etf_holdings


def test_normalize_etf_holdings_frame_accepts_chinese_export_columns():
    raw = pd.DataFrame(
        [
            {
                "資料日期": "2026-06-12",
                "ETF代號": "00878",
                "ETF名稱": "國泰永續高股息",
                "成分股代號": "2382",
                "成分股名稱": "廣達",
                "權重": "10.51%",
                "股數": "168,840,000",
                "市值": "63,320,000,000",
            }
        ]
    )

    normalized = update_etf_holdings.normalize_holdings_frame(raw, source="issuer_csv")

    assert normalized.to_dict("records") == [
        {
            "as_of_date": pd.Timestamp("2026-06-12"),
            "etf_code": "00878",
            "etf_name": "國泰永續高股息",
            "constituent_code": "2382",
            "constituent_name": "廣達",
            "weight_pct": 10.51,
            "shares": 168840000.0,
            "market_value_twd": 63320000000.0,
            "source": "issuer_csv",
            "source_url": None,
        }
    ]
