#!/usr/bin/env python3
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, List, Dict
from bs4 import BeautifulSoup
import requests
import pandas as pd
from dotenv import load_dotenv

from google import genai
from pydantic import BaseModel, Field

LOGGER = logging.getLogger("advanced_sentiment_analyzer")
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
SENTIMENT_OUTPUT = PROCESSED / "sentiment_latest.parquet"

load_dotenv()  # load .env to get GEMINI_API_KEY

class StockSentiment(BaseModel):
    stock_code: str = Field(description="The stock code, e.g., '2330' or '0050'")
    stock_name: str = Field(description="The stock name, e.g., '台積電'")
    bullish_score: int = Field(description="Bullish intensity from 0 to 100")
    bearish_score: int = Field(description="Bearish intensity from 0 to 100")
    temperature: int = Field(description="Heat or frequency of discussion from 0 to 100")
    keywords: list[str] = Field(description="Up to 3 keywords summarizing the sentiment context")

class BatchSentimentResult(BaseModel):
    results: list[StockSentiment]


def fetch_ptt_stock_news(pages: int = 3) -> list[str]:
    """Scrape recent titles from PTT Stock board."""
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    url = "https://www.ptt.cc/bbs/Stock/index.html"
    news_items = []
    
    try:
        for _ in range(pages):
            res = requests.get(url, headers=headers, cookies={"over18": "1"}, timeout=10)
            if res.status_code != 200:
                break
            soup = BeautifulSoup(res.text, "html.parser")
            
            for ent in soup.select("div.r-ent"):
                title_elem = ent.select_one("div.title a")
                if title_elem:
                    title_text = title_elem.text.strip()
                    news_items.append(f"[PTT] {title_text}")
            
            prev_link = soup.select_one('a.btn.wide:-soup-contains("‹ 上頁")')
            if not prev_link:
                btn_group = soup.select('div.btn-group-paging a.btn.wide')
                if len(btn_group) >= 2 and '上頁' in btn_group[1].text:
                    prev_link = btn_group[1]
                
            if prev_link and 'href' in prev_link.attrs:
                url = "https://www.ptt.cc" + prev_link['href']
                time.sleep(0.5)
            else:
                break
    except Exception as e:
        LOGGER.error(f"Error fetching PTT news: {e}")
    
    return news_items


def fetch_threads_stock_news() -> list[str]:
    """Scrape Threads using Playwright for Taiwan stock keywords."""
    news_items = []
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = context.new_page()
            LOGGER.info("Fetching Threads for '台股'")
            page.goto("https://www.threads.net/search?q=%E5%8F%B0%E8%82%A1", timeout=20000)
            
            try:
                page.wait_for_selector("div[data-pressable-container='true']", timeout=10000)
                # Scroll to load more
                page.evaluate("window.scrollBy(0, 2000)")
                time.sleep(2)
                
                posts = page.locator("div[data-pressable-container='true']").all_inner_texts()
                for post in posts:
                    cleaned = " ".join(post.split())
                    if cleaned and len(cleaned) > 5:
                        news_items.append(f"[Threads] {cleaned}")
            except Exception as e:
                LOGGER.warning(f"Could not find threads posts container: {e}")
                
            browser.close()
    except Exception as e:
        LOGGER.error(f"Error fetching Threads news: {e}")
    
    # Deduplicate and limit
    unique_items = list(set(news_items))
    return unique_items[:50]


def analyze_sentiments_with_gemini(posts: list[str]) -> List[Dict]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        LOGGER.error("GEMINI_API_KEY not found in environment.")
        return []

    if not posts:
        return []

    client = genai.Client(api_key=api_key)
    
    prompt = """
    你是一位專業的台股分析師。請分析以下來自 PTT 股版和社群的熱門文章標題/內文。
    請從中萃取出有被提及的「台灣股票」，並評估其情緒。
    
    對於每一檔提到的股票，請提供：
    1. stock_code (股票代號，例如 '2330')
    2. stock_name (股票名稱，例如 '台積電')
    3. bullish_score (多方強度，0~100)
    4. bearish_score (空方強度，0~100)
    5. temperature (討論熱度，0~100，提及越多次或情緒越激動越高)
    6. keywords (最多3個代表性的關鍵字，例如 '法說會超預期', '營收創高', '外資倒貨')
    
    若該貼文內容只是閒聊沒有提及特定股票，請忽略。
    
    社群貼文內容如下：
    """ + "\n".join(posts)

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': BatchSentimentResult,
            },
        )
        data = response.parsed
        if data and hasattr(data, 'results'):
            # Convert to dictionary format
            return [
                {
                    "stock_code": item.stock_code,
                    "stock_id": item.stock_code,
                    "stock_name": item.stock_name,
                    "mention_count": 1, # Mock since we do batch
                    "sentiment_score": (item.bullish_score - item.bearish_score) / 100.0,
                    "sentiment_temperature": item.temperature,
                    "headline_samples": item.keywords,
                    "bullish_score": item.bullish_score,
                    "bearish_score": item.bearish_score
                }
                for item in data.results
            ]
    except Exception as e:
        LOGGER.error(f"Gemini API error: {e}")
        
    return []


def build_sentiment_records() -> pd.DataFrame:
    posts = fetch_ptt_stock_news(pages=3)
    threads_posts = fetch_threads_stock_news()
    posts.extend(threads_posts)
    
    results = analyze_sentiments_with_gemini(posts)
    if not results:
        return pd.DataFrame(columns=[
            "stock_code", "stock_id", "stock_name", "mention_count", 
            "sentiment_score", "sentiment_temperature", "headline_samples",
            "bullish_score", "bearish_score"
        ])
        
    df = pd.DataFrame(results)
    # Deduplicate in case Gemini returned same stock twice
    df = df.groupby("stock_code").first().reset_index()
    return df.sort_values("sentiment_temperature", ascending=False).reset_index(drop=True)


def _to_float(value: Any) -> float | None:
    import math
    try:
        num = float(str(value).replace(",", "").strip())
    except Exception:
        return None
    if math.isnan(num) or math.isinf(num):
        return None
    return num


def build_macro_payload() -> dict[str, Any]:
    PUBLIC_DATA = ROOT / "public" / "data"
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


def update_advanced_sentiment() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Starting advanced sentiment analysis...")
    sentiment_df = build_sentiment_records()
    sentiment_df.to_parquet(SENTIMENT_OUTPUT, index=False)
    
    # Write macro
    MACRO_OUTPUT = PROCESSED / "macro_latest.json"
    MACRO_OUTPUT.write_text(json.dumps(build_macro_payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    
    LOGGER.info(f"Generated sentiment analysis for {len(sentiment_df)} stocks.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    update_advanced_sentiment()
