import pandas as pd
from pathlib import Path

processed_root = Path("data/processed")
stock_alpha = pd.read_parquet(processed_root / "stock_alpha_breakdown.parquet")
inst = pd.read_parquet(processed_root / "institutional_flow.parquet")

latest_date = inst['trade_date'].max()
inst_latest = inst[inst['trade_date'] == latest_date].copy()

# Map latest institutional flow back to stock_alpha
for col in ['foreign_net_shares', 'trustee_net_shares', 'dealer_net_shares', 'three_party_net_shares']:
    mapping = inst_latest.set_index('stock_code')[col].to_dict()
    stock_alpha[col] = stock_alpha['stock_code'].map(mapping)

stock_alpha.to_parquet(processed_root / "stock_alpha_breakdown.parquet", index=False)
print("Patched stock_alpha_breakdown.parquet")
