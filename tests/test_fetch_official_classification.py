from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "fetch_official_classification.py"


def load_module():
    spec = importlib.util.spec_from_file_location("fetch_official_classification", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_merge_classification_deduplicates_existing_and_new_rows() -> None:
    module = load_module()
    existing = pd.DataFrame(
        [
            {"stock_code": "2330", "stock_name": "台積電舊", "market": "TWSE", "industry": "半導體舊", "sector": "半導體舊"},
            {"stock_code": "2330", "stock_name": "台積電較新", "market": "TWSE", "industry": "半導體", "sector": "半導體"},
            {"stock_code": "00878", "stock_name": "國泰永續高股息", "market": "TWSE", "industry": "其他", "sector": "其他"},
        ]
    )
    incoming = pd.DataFrame(
        [
            {"stock_code": "2330", "stock_name": "台積電", "market": "TWSE", "industry": "半導體業", "sector": "半導體業"},
            {"stock_code": "00878", "stock_name": "國泰永續高股息", "market": "TWSE", "industry": "ETF", "sector": "ETF"},
            {"stock_code": "00878", "stock_name": "國泰永續高股息", "market": "TWSE", "industry": "ETF", "sector": "ETF"},
            {"stock_code": "6488", "stock_name": "環球晶", "market": "TPEx", "industry": "半導體業", "sector": "半導體業"},
        ]
    )

    merged = module.merge_classification_frames(existing, incoming)

    assert not merged["stock_code"].duplicated().any()
    assert set(merged["stock_code"]) == {"2330", "00878", "6488"}
    assert merged.loc[merged["stock_code"] == "2330", "stock_name"].item() == "台積電"
    assert merged.loc[merged["stock_code"] == "00878", "industry"].item() == "ETF"
    assert merged.loc[merged["stock_code"] == "6488", "market"].item() == "TPEx"
