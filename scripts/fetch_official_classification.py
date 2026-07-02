#!/usr/bin/env python3
import json
import logging
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

LOGGER = logging.getLogger("fetch_official_classification")
ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"


def fetch_isin(mode: int, market_name: str) -> pd.DataFrame:
    """Fetch ISIN classification from TWSE site.
    mode=2 (TWSE 上市)
    mode=4 (TPEx 上櫃)
    """
    url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}"
    try:
        LOGGER.info(f"Fetching {market_name} classification from {url}")
        res = requests.get(url, timeout=15)
        res.encoding = "big5"
        soup = BeautifulSoup(res.text, "html.parser")
        
        tables = soup.find_all("table")
        if not tables or len(tables) < 2:
            LOGGER.warning(f"No table found for {market_name}")
            return pd.DataFrame()
            
        table = tables[1]
        rows = table.find_all("tr")
        data = []
        for row in rows:
            cols = row.find_all("td")
            if len(cols) == 7:
                text_cols = [c.get_text(strip=True) for c in cols]
                # Columns: 有價證券代號及名稱, ISIN, 上市日, 市場別, 產業別, CFICode, 備註
                code_name = text_cols[0].split("\u3000") # they use full-width space
                if len(code_name) >= 2:
                    code = code_name[0].strip()
                    name = code_name[1].strip()
                    industry = text_cols[4]
                    if not industry:
                        # Fallback for ETFs or others that have no industry but have a type
                        if "ETF" in name or "基金" in name or "ETF" in text_cols[5]:
                            industry = "ETF"
                        elif "ETN" in name:
                            industry = "ETN"
                        else:
                            industry = "其他"
                    
                    data.append({
                        "stock_code": code,
                        "stock_name": name,
                        "market": market_name,
                        "industry": industry,
                        "sector": industry
                    })
        
        return pd.DataFrame(data)
    except Exception as e:
        LOGGER.error(f"Error fetching {market_name}: {e}")
        return pd.DataFrame()


def merge_classification_frames(existing_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for source in (existing_df, new_df):
        if source.empty:
            continue
        frame = source.copy()
        if "stock_code" not in frame.columns and "stock_id" in frame.columns:
            frame["stock_code"] = frame["stock_id"].astype(str)
        if "stock_code" not in frame.columns:
            continue
        frame["stock_code"] = frame["stock_code"].astype(str).str.strip()
        frame = frame[frame["stock_code"] != ""].copy()
        frames.append(frame)

    if not frames:
        return pd.DataFrame(columns=["stock_code", "stock_id", "stock_name", "market", "industry", "sector"])

    merged = pd.concat(frames, ignore_index=True, sort=False)
    merged = merged.drop_duplicates("stock_code", keep="last").reset_index(drop=True)
    merged["stock_id"] = merged.get("stock_id", merged["stock_code"]).fillna(merged["stock_code"]).astype(str)
    if "sector" not in merged.columns and "industry" in merged.columns:
        merged["sector"] = merged["industry"]
    return merged


def update_sector_classification() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / "sector_classification.parquet"
    
    twse_df = fetch_isin(2, "TWSE")
    tpex_df = fetch_isin(4, "TPEx")
    
    new_df = pd.concat([twse_df, tpex_df], ignore_index=True)
    if new_df.empty:
        LOGGER.error("No data fetched from TWSE/TPEx.")
        return

    if out_path.exists():
        existing_df = pd.read_parquet(out_path)
        final_df = merge_classification_frames(existing_df, new_df)
    else:
        final_df = merge_classification_frames(pd.DataFrame(), new_df)

    final_df.to_parquet(out_path, index=False)
    LOGGER.info(f"Updated sector_classification.parquet with {len(final_df)} records.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    update_sector_classification()
