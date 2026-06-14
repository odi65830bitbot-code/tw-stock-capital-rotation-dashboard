import pandas as pd
from pathlib import Path

processed_root = Path("data/processed")
alpha_df = pd.read_parquet(processed_root / "stock_alpha_breakdown.parquet") if (processed_root / "stock_alpha_breakdown.parquet").exists() else pd.DataFrame()

if not alpha_df.empty:
    unknowns = alpha_df[alpha_df["industry"] == "UNKNOWN"]
    # latest date only
    latest_date = unknowns["trade_date"].max()
    unknowns = unknowns[unknowns["trade_date"] == latest_date]
    print("Latest date unknowns:", len(unknowns))
    
    # filter out starting with 00
    non_00 = unknowns[~unknowns["stock_code"].str.startswith("00")]
    print("Non-00 unknowns:", len(non_00))
    print(non_00[["stock_code", "stock_name"]].head(20))
    
    # how many start with 0
    start_0 = unknowns[unknowns["stock_code"].str.startswith("0")]
    print("Start with 0:", len(start_0))
    
    # Warrants usually have length 6
    warrants = unknowns[unknowns["stock_code"].str.len() > 4]
    print("Length > 4:", len(warrants))
    
    # Are there any length 4 unknowns?
    len4 = unknowns[unknowns["stock_code"].str.len() == 4]
    print("Length == 4 unknowns:", len(len4))
    print(len4[["stock_code", "stock_name"]].head(20))
