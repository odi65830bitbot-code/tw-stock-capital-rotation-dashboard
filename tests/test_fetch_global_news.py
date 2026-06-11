from __future__ import annotations

import importlib
import json


def test_fetch_global_news_parses_rss_and_writes_latest_json(tmp_path, monkeypatch):
    news = importlib.import_module("scripts.fetch_global_news")
    public_data = tmp_path / "public" / "data"
    monkeypatch.setattr(news, "PUBLIC_DATA", public_data)

    rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss><channel>
      <item><title>台股資金回流</title><link>https://example.com/1</link><pubDate>Thu, 11 Jun 2026 08:00:00 GMT</pubDate></item>
      <item><title>全球財經觀察</title><link>https://example.com/2</link><pubDate>Thu, 11 Jun 2026 07:00:00 GMT</pubDate></item>
    </channel></rss>
    """

    class Response:
        text = rss

        def raise_for_status(self):
            return None

    def fake_get(url, timeout):
        assert "news.google.com/rss/search" in url
        assert timeout == 20
        return Response()

    monkeypatch.setattr(news.requests, "get", fake_get)

    payload = news.fetch_and_write_global_news()
    saved = json.loads((public_data / "global_news_latest.json").read_text(encoding="utf-8"))

    assert payload["records"] == [
        {"title": "台股資金回流", "link": "https://example.com/1", "pubDate": "Thu, 11 Jun 2026 08:00:00 GMT"},
        {"title": "全球財經觀察", "link": "https://example.com/2", "pubDate": "Thu, 11 Jun 2026 07:00:00 GMT"},
    ]
    assert saved["records"] == payload["records"]
    assert "generated_at" in saved
