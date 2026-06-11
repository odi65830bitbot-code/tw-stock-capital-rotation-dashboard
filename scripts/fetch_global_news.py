#!/usr/bin/env python3
"""Fetch latest global finance news from Google News RSS."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DATA = ROOT / "public" / "data"
TAIPEI = ZoneInfo("Asia/Taipei")
RSS_URL = "https://news.google.com/rss/search?q=%E8%B2%A1%E7%B6%93+when:1d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"


def _now_iso() -> str:
    return datetime.now(TAIPEI).replace(microsecond=0).isoformat()


def parse_rss(xml_text: str, limit: int = 15) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    records: list[dict[str, str]] = []
    for item in root.findall(".//item")[:limit]:
        title = item.findtext("title", default="").strip()
        link = item.findtext("link", default="").strip()
        pub_date = item.findtext("pubDate", default="").strip()
        if not title or not link:
            continue
        records.append({"title": title, "link": link, "pubDate": pub_date})
    return records


def fetch_and_write_global_news() -> dict[str, object]:
    response = requests.get(RSS_URL, timeout=20)
    response.raise_for_status()
    payload = {
        "generated_at": _now_iso(),
        "records": parse_rss(response.text, limit=15),
    }
    PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
    (PUBLIC_DATA / "global_news_latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    payload = fetch_and_write_global_news()
    print(f"Fetched {len(payload['records'])} global finance news records")


if __name__ == "__main__":
    main()
