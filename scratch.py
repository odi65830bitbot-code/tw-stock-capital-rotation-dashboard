import pandas as pd
from pathlib import Path

processed_root = Path("data/processed")
sector_df = pd.read_parquet(processed_root / "sector_classification.parquet") if (processed_root / "sector_classification.parquet").exists() else pd.DataFrame()
alpha_df = pd.read_parquet(processed_root / "stock_alpha_breakdown.parquet") if (processed_root / "stock_alpha_breakdown.parquet").exists() else pd.DataFrame()

if not alpha_df.empty:
    unknowns = alpha_df[alpha_df["industry"] == "UNKNOWN"]
    print("Total unknowns:", len(unknowns))
    print("Unknowns starting with '00':", len(unknowns[unknowns["stock_code"].str.startswith("00")]))
    print(unknowns[["stock_code", "stock_name"]].head(20))
else:
    print("No alpha df")
