from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.official_source_registry import TWSE_DAILY_PRICE
from src.data.twse_client import TWSEClient


class _FakeResponse:
    def __init__(self, *, status: int = 200, text: str = "", headers: dict | None = None, payload=None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}
        self._payload = payload
        self.content = text.encode("utf-8")

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, responses):
        self._responses = responses
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, timeout=None, headers=None):
        self.calls.append((url, headers or {}))
        response = self._responses.pop(0)
        return response


def test_twse_fetch_prefers_json_and_saves_json_csv(tmp_path: Path):
    target_date = date(2026, 6, 6)
    fake_payload = [
        {"Date": "1150606", "Code": "2330", "Name": "台積電", "TradeVolume": "100", "TradeValue": "200"}
    ]
    session = _FakeSession([
        _FakeResponse(
            text=json.dumps(fake_payload),
            headers={"Content-Type": "application/json"},
            payload=fake_payload,
        )
    ])

    client = TWSEClient(raw_root=tmp_path / "raw", session=session)
    result = client.fetch_daily_price(target_date)

    assert result.records == fake_payload
    assert (tmp_path / "raw" / "twse" / "20260606" / f"{TWSE_DAILY_PRICE.name}.json").exists()
    assert (tmp_path / "raw" / "twse" / "20260606" / f"{TWSE_DAILY_PRICE.name}.csv").exists()


def test_twse_fetch_fallback_to_official_csv_when_json_invalid(tmp_path: Path):
    target_date = date(2026, 6, 6)
    bad_json = _FakeResponse(
        text="<!html>",
        headers={"Content-Type": "text/html"},
        payload={"text": "not-json"},
    )
    csv_text = "Date,Code,Name,TradeVolume,TradeValue\n1150606,2330,台積電,100,200\n"
    csv_resp = _FakeResponse(
        text=csv_text,
        headers={"Content-Type": "text/csv"},
    )
    session = _FakeSession([bad_json, csv_resp])

    client = TWSEClient(raw_root=tmp_path / "raw", session=session)
    result = client.fetch_daily_price(target_date)

    assert result.records == [{"Date": "1150606", "Code": "2330", "Name": "台積電", "TradeVolume": "100", "TradeValue": "200"}]
    assert result.source == "twse"
    assert result.trade_date.isoformat() == "2026-06-06"


def test_twse_institutional_flow_uses_gregorian_date_query(tmp_path: Path):
    target_date = date(2026, 6, 6)
    payload = [{"date": "20260606", "證券代號": "2330", "證券名稱": "台積電", "三大法人買賣超股數": "10"}]
    csv_text = "date,證券代號,證券名稱,三大法人買賣超股數\n20260606,2330,台積電,10\n"
    # 即使回傳 JSON 成功，也要驗證 URL 是以西元日期查詢
    json_resp = _FakeResponse(
        text=json.dumps(payload),
        headers={"Content-Type": "application/json"},
        payload=payload,
    )
    session = _FakeSession([json_resp])
    client = TWSEClient(raw_root=tmp_path / "raw", session=session)
    client.fetch_institutional_flow(target_date)

    called_url, _ = session.calls[0]
    assert "date=20260606" in called_url
    assert "selectType=ALL" in called_url
    assert "T86" in called_url


def test_twse_institutional_flow_csv_fallback_skips_title_and_cleans_excel_codes(tmp_path: Path):
    target_date = date(2026, 6, 6)
    bad_json = _FakeResponse(
        text="<!html>",
        headers={"Content-Type": "text/html"},
        payload={"text": "not-json"},
    )
    csv_text = "\n".join(
        [
            '"115年06月06日 三大法人買賣超日報"',
            '"證券代號","證券名稱","三大法人買賣超股數",',
            '="00632R","元大台灣50反1","50,555,027",',
            '"3231","緯創","1,234",',
        ]
    )
    csv_resp = _FakeResponse(
        text=csv_text,
        headers={"Content-Type": "text/csv"},
    )
    session = _FakeSession([bad_json, csv_resp])

    client = TWSEClient(raw_root=tmp_path / "raw", session=session)
    result = client.fetch_institutional_flow(target_date)

    assert result.records[0]["證券代號"] == "00632R"
    assert result.records[1]["證券代號"] == "3231"
    assert result.records[0]["date"] == "20260606"
