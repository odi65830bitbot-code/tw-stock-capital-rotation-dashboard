from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.finmind_client import FinMindClient


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _RetrySession:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        if len(self.calls) < 3:
            return _FakeResponse({"msg": "rate limited", "data": []}, status_code=429)
        return _FakeResponse({"data": [{"stock_id": "2330", "stock_name": "台積電"}]})


def test_token_missing_has_clear_error(monkeypatch, tmp_path):
    monkeypatch.delenv("FINMIND_TOKEN", raising=False)
    monkeypatch.delenv("FINMIND_API_TOKEN", raising=False)

    client = FinMindClient(raw_root=tmp_path / "raw", cache_root=tmp_path / "cache", env_file=tmp_path / ".env")

    with pytest.raises(RuntimeError, match="FINMIND_TOKEN"):
        client.fetch_dataset("TaiwanStockInfo", start_date="2026-01-01", end_date="2026-01-02")


def test_calls_taiwan_stock_info_and_writes_raw_and_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("FINMIND_TOKEN", "secret-token")
    session = _RetrySession()
    client = FinMindClient(
        raw_root=tmp_path / "raw",
        cache_root=tmp_path / "cache",
        session=session,
        sleep_seconds=0,
    )

    result = client.fetch_dataset("TaiwanStockInfo", start_date="2026-01-01", end_date="2026-01-02")

    assert len(session.calls) == 3
    assert session.calls[-1]["params"]["dataset"] == "TaiwanStockInfo"
    assert session.calls[-1]["headers"] == {"Authorization": "Bearer secret-token"}
    assert result.status == "ok"
    assert result.dataframe.iloc[0]["stock_id"] == "2330"
    assert result.raw_json_path.exists()
    assert result.cache_path.exists()
    payload = json.loads(result.raw_json_path.read_text(encoding="utf-8"))
    assert payload["data"][0]["stock_name"] == "台積電"


def test_api_failure_retries_without_logging_token(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("FINMIND_TOKEN", "sensitive-token")
    session = _RetrySession()
    client = FinMindClient(
        raw_root=tmp_path / "raw",
        cache_root=tmp_path / "cache",
        session=session,
        sleep_seconds=0,
    )

    with caplog.at_level(logging.WARNING):
        client.fetch_dataset("TaiwanStockInfo", start_date="2026-01-01", end_date="2026-01-02")

    assert len(session.calls) == 3
    assert "sensitive-token" not in caplog.text
