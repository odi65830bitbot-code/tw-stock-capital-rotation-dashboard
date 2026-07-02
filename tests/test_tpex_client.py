from __future__ import annotations

import json
from datetime import date
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data.tpex_client import TPEXClient


class _FakeResponse:
    def __init__(self, *, text: str = "", headers=None, payload=None):
        self.text = text
        self.headers = headers or {}
        self._payload = payload
        self.status_code = 200
        self.content = text.encode("utf-8")

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, responses):
        self._responses = responses
        self.calls = []

    def get(self, url, timeout=None, headers=None):
        self.calls.append((url, headers or {}))
        return self._responses.pop(0)


def test_tpex_fetch_success_json(tmp_path):
    target = date(2026, 6, 6)
    payload = [{"Date": "1150606", "SecuritiesCompanyCode": "006201", "CompanyName": "元大富櫃50", "Close": "48.12"}]
    session = _FakeSession([
        _FakeResponse(
            text=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            payload=payload,
        )
    ])
    client = TPEXClient(raw_root=tmp_path / "raw", session=session)
    result = client.fetch_daily_price(target)
    assert result.records == payload
    assert result.trade_date == date(2026, 6, 6)
    assert (tmp_path / "raw" / "tpex" / "20260606" / "tpex_daily_price.json").exists()
    assert (tmp_path / "raw" / "tpex" / "20260606" / "tpex_daily_price.csv").exists()


def test_tpex_fetch_fallback_on_json_non_json(tmp_path):
    target = date(2026, 6, 6)
    bad_json = _FakeResponse(text="<html />", headers={"Content-Type": "text/html"})
    csv_text = "Date,SecuritiesCompanyCode,CompanyName,Close,Open,High,Low,TradingShares,TransactionAmount\n1150606,006201,元大富櫃50,48.12,49,50,47,123,500\n"
    csv_resp = _FakeResponse(text=csv_text, headers={"Content-Type": "text/csv"})
    session = _FakeSession([bad_json, csv_resp])
    client = TPEXClient(raw_root=tmp_path / "raw", session=session)
    result = client.fetch_institutional_flow(target)
    assert result.source == "tpex"
    assert result.trade_date == date(2026, 6, 6)
    assert result.records[0]["Date"] == "1150606"
    assert "3itrade_hedge_result.php" in session.calls[0][0]


def test_tpex_daily_price_endpoint_supports_historical_date(tmp_path):
    target = date(2026, 6, 6)
    payload = [{"Date": "1150606", "SecuritiesCompanyCode": "006201", "CompanyName": "元大富櫃50", "Close": "48.12"}]
    session = _FakeSession([
        _FakeResponse(
            text=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            payload=payload,
        )
    ])
    client = TPEXClient(raw_root=tmp_path / "raw", session=session)
    client.fetch_daily_price(target)
    called_url = session.calls[0][0]
    assert "afterTrading/dailyQuotes" in called_url
    assert "date=115/06/06" in called_url


def test_tpex_daily_price_uses_historical_query_date_and_parses_tables(tmp_path):
    target = date(2026, 6, 23)
    payload = {
        "date": "20260623",
        "tables": [
            {
                "date": "115/06/23",
                "fields": ["代號", "名稱", "收盤 ", "漲跌", "開盤 ", "最高 ", "最低", "成交股數  ", " 成交金額(元)", " 成交筆數 "],
                "data": [
                    ["00679B", "元大美債20年", "26.86", "-0.11", "26.87", "26.87", "26.83", "22,222,000", "596,625,830", "2,410"],
                ],
            }
        ],
    }
    session = _FakeSession(
        [
            _FakeResponse(
                text=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                payload=payload,
            )
        ]
    )
    client = TPEXClient(raw_root=tmp_path / "raw", session=session)

    result = client.fetch_daily_price(target)

    called_url = session.calls[0][0]
    assert "afterTrading/dailyQuotes" in called_url
    assert "date=115/06/23" in called_url
    assert result.trade_date == target
    assert result.records[0]["Date"] == "115/06/23"
    assert result.records[0]["SecuritiesCompanyCode"] == "00679B"
    assert result.records[0]["TradingShares"] == "22,222,000"
