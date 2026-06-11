#!/usr/bin/env python3
"""Build simple news sentiment and macro filters for the v5 quant model."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
PUBLIC_DATA = ROOT / "public" / "data"
SENTIMENT_OUTPUT = PROCESSED / "sentiment_latest.parquet"
MACRO_OUTPUT = PROCESSED / "macro_latest.json"
SENTIMENT_COLUMNS = [
    "stock_code",
    "stock_id",
    "stock_name",
    "mention_count",
    "sentiment_score",
    "sentiment_temperature",
    "headline_samples",
]

POSITIVE_WORDS = {
    "強勁",
    "成長",
    "創高",
    "看好",
    "利多",
    "上修",
    "優於預期",
    "訂單",
    "突破",
    "旺",
    "回升",
}
NEGATIVE_WORDS = {
    "疲弱",
    "下修",
    "衰退",
    "利空",
    "虧損",
    "過熱",
    "警戒",
    "賣壓",
    "低於預期",
    "跌破",
}


def _score_title(title: str) -> float:
    pos = sum(1 for word in POSITIVE_WORDS if word in title)
    neg = sum(1 for word in NEGATIVE_WORDS if word in title)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


def _to_float(value: Any) -> float | None:
    try:
        num = float(str(value).replace(",", "").strip())
    except Exception:
        return None
    if math.isnan(num) or math.isinf(num):
        return None
    return num


def load_news() -> list[dict[str, Any]]:
    path = PUBLIC_DATA / "global_news_latest.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    records = payload.get("records") or payload.get("items") or []
    return records if isinstance(records, list) else []


def load_universe() -> pd.DataFrame:
    for name in ["sector_classification.parquet", "stock_alpha.parquet", "daily_price.parquet"]:
        path = PROCESSED / name
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if {"stock_code", "stock_name"}.issubset(df.columns):
            return df[["stock_code", "stock_name"]].dropna().drop_duplicates()
    return pd.DataFrame(columns=["stock_code", "stock_name"])


def build_sentiment_records(news: list[dict[str, Any]], universe: pd.DataFrame) -> pd.DataFrame:
    if not news or universe.empty:
        return pd.DataFrame(columns=SENTIMENT_COLUMNS)

    records: list[dict[str, Any]] = []
    for _, stock in universe.drop_duplicates("stock_code").iterrows():
        code = str(stock.get("stock_code") or "").strip()
        name = str(stock.get("stock_name") or "").strip()
        if not code or not name:
            continue
        matched: list[str] = []
        scores: list[float] = []
        for item in news:
            title = str(item.get("title") or "")
            if code in title or name in title:
                matched.append(title)
                scores.append(_score_title(title))
        if not matched:
            continue
        score = round(sum(scores) / len(scores), 4) if scores else 0.0
        temperature = min(100.0, round(len(matched) * 25 + max(score, 0) * 45, 2))
        records.append(
            {
                "stock_code": code,
                "stock_id": code,
                "stock_name": name,
                "mention_count": len(matched),
                "sentiment_score": score,
                "sentiment_temperature": temperature,
                "headline_samples": matched[:3],
            }
        )
    if not records:
        return pd.DataFrame(columns=SENTIMENT_COLUMNS)
    return pd.DataFrame(records, columns=SENTIMENT_COLUMNS).sort_values(["sentiment_temperature", "mention_count"], ascending=False).reset_index(drop=True)


def build_macro_payload() -> dict[str, Any]:
    path = PUBLIC_DATA / "market_latest.json"
    records = []
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            records = payload.get("records") or []
        except Exception:
            records = []
    risk = "neutral"
    taiex = next((row for row in records if str(row.get("index_name")) in {"TAIEX", "發行量加權股價指數", "加權指數"}), None)
    if isinstance(taiex, dict):
        change_pct = _to_float(taiex.get("change_pct"))
        if change_pct is not None:
            if change_pct <= -2:
                risk = "risk_off"
            elif change_pct >= 1:
                risk = "risk_on"
    return {
        "status": "ok" if records else "warning",
        "market_regime": risk,
        "source": "public/data/market_latest.json",
        "records": records,
    }


def main() -> int:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    news = load_news()
    universe = load_universe()
    sentiment = build_sentiment_records(news, universe)
    sentiment.to_parquet(SENTIMENT_OUTPUT, index=False)
    MACRO_OUTPUT.write_text(json.dumps(build_macro_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ok" if not sentiment.empty else "warning",
                "rows": int(len(sentiment)),
                "news_records": len(news),
                "output": str(SENTIMENT_OUTPUT),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
