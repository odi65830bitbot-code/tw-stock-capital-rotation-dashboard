from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.stock_lookup import find_stock_matches, get_exact_or_best_match


def test_stock_lookup_supports_code_and_name_query():
    daily = pd.DataFrame(
        [
            {"market": "TWSE", "stock_code": "2330", "stock_name": "台積電", "industry": "半導體業"},
            {"market": "TWSE", "stock_code": "3231", "stock_name": "緯創", "industry": "電腦及週邊設備業"},
        ]
    )

    by_code = get_exact_or_best_match("2330", daily)
    by_name = get_exact_or_best_match("台積", daily)

    assert by_code is not None
    assert by_code.stock_id == "2330"
    assert by_code.market == "TWSE"
    assert by_name is not None
    assert by_name.stock_name == "台積電"


def test_stock_lookup_returns_empty_list_for_unknown_stock():
    daily = pd.DataFrame(
        [{"market": "TWSE", "stock_code": "2330", "stock_name": "台積電", "industry": "半導體業"}]
    )

    assert find_stock_matches("不存在", daily) == []
