from __future__ import annotations

import importlib

import pandas as pd


def test_fetch_institutional_marks_permission_or_plan_errors(monkeypatch):
    txf = importlib.import_module("scripts.update_txf_after_hours")

    def raise_permission_error(*args, **kwargs):
        raise RuntimeError("HTTP 400: permission denied, sponsor required")

    monkeypatch.setattr(txf, "_request_finmind", raise_permission_error)

    frame, error, status = txf._fetch_institutional("2026-06-01", "2026-06-10")

    assert frame.empty
    assert "sponsor required" in error
    assert status == "permission_or_plan_required"


def test_fetch_institutional_normalizes_date(monkeypatch):
    txf = importlib.import_module("scripts.update_txf_after_hours")

    def fake_request(*args, **kwargs):
        return (
            [
                {
                    "date": "2026/06/10",
                    "futures_id": "TX",
                    "institutional_investors": "Foreign_Investor",
                    "long_deal_volume": 10,
                    "short_deal_volume": 3,
                }
            ],
            {"status": 200},
        )

    monkeypatch.setattr(txf, "_request_finmind", fake_request)

    frame, error, status = txf._fetch_institutional("2026-06-01", "2026-06-10")

    assert error is None
    assert status == "ok"
    assert frame.iloc[0]["date"] == "2026-06-10"
    assert frame.iloc[0]["futures_id"] == "TX"
