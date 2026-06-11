import json
import logging
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from modules.finmind_client import FinMindClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
LOGGER = logging.getLogger("patch_margin")

ROOT = Path(__file__).resolve().parents[1]
RECOMMENDATIONS_PATH = ROOT / "public" / "data" / "recommendations_v4_latest.json"
MARGIN_PARQUET_PATH = ROOT / "data" / "processed" / "finmind_margin.parquet"

def main():
    if not RECOMMENDATIONS_PATH.exists():
        LOGGER.error("recommendations_v4_latest.json not found")
        return
    
    with open(RECOMMENDATIONS_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    
    records = payload.get("records") or payload.get("items") or []
    stock_ids = []
    for r in records:
        sid = r.get("stock_id") or r.get("stock_code")
        if sid:
            stock_ids.append(str(sid).strip())
            
    stock_ids = list(dict.fromkeys(stock_ids))
    LOGGER.info("Found %d stock ids from recommendations", len(stock_ids))
    
    client = FinMindClient()
    new_frames = []
    
    for idx, sid in enumerate(stock_ids, 1):
        LOGGER.info("[%d/%d] Fetching margin for %s", idx, len(stock_ids), sid)
        try:
            res = client.fetch_dataset(
                "TaiwanStockMarginPurchaseShortSale",
                stock_id=sid,
                start_date="2026-06-08",
                end_date="2026-06-10",
                allow_unavailable=True
            )
            if res.status == "ok" and not res.dataframe.empty:
                new_frames.append(res.dataframe)
            time.sleep(0.3)
        except Exception as exc:
            LOGGER.error("Failed to fetch %s: %s", sid, exc)
            
    if not new_frames:
        LOGGER.warning("No new margin data fetched")
        return
        
    incoming = pd.concat(new_frames, ignore_index=True)
    incoming["date"] = pd.to_datetime(incoming["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    
    existing = pd.read_parquet(MARGIN_PARQUET_PATH) if MARGIN_PARQUET_PATH.exists() else pd.DataFrame()
    if not existing.empty:
        existing["date"] = pd.to_datetime(existing["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        merged = pd.concat([existing, incoming], ignore_index=True)
    else:
        merged = incoming
        
    merged = merged.drop_duplicates(subset=["date", "stock_id"], keep="last")
    merged.to_parquet(MARGIN_PARQUET_PATH, index=False)
    LOGGER.info("Merged margin data. Total rows in parquet: %d", len(merged))

if __name__ == "__main__":
    main()
