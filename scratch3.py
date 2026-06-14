import pandas as pd
from pathlib import Path

processed_root = Path("data/processed")
daily_price_df = pd.read_parquet(processed_root / "daily_price.parquet") if (processed_root / "daily_price.parquet").exists() else pd.DataFrame()
sector_df = pd.read_parquet(processed_root / "sector_classification.parquet") if (processed_root / "sector_classification.parquet").exists() else pd.DataFrame()

existing_codes = set(sector_df["stock_code"].astype(str)) if not sector_df.empty else set()
synthesized_sectors = []
for _, row in daily_price_df.drop_duplicates(subset=["stock_code"], keep="last").iterrows():
    code = str(row["stock_code"])
    if code in existing_codes:
        continue
    name = str(row.get("stock_name", "")).upper()
    industry = None
    if code.startswith("00") or "ETF" in name:
        industry = "ETF"
    elif code.startswith("01"):
        industry = "REITs"
    elif code.startswith("02") or "ETN" in name:
        industry = "ETN"
    elif code.startswith("91") or "-DR" in name:
        industry = "DR(存託憑證)"
        
    if industry:
        synthesized_sectors.append({
            "industry": industry,
            "stock_code": code,
            "stock_name": row.get("stock_name"),
        })

print(f"Synthesized {len(synthesized_sectors)} sectors.")
syn_df = pd.DataFrame(synthesized_sectors)
if not syn_df.empty:
    print(syn_df["industry"].value_counts())
    print("Sample ETF:", syn_df[syn_df["industry"] == "ETF"].head())
