import pandas as pd
from pathlib import Path

processed_root = Path("data/processed")
stock_alpha = pd.read_parquet(processed_root / "stock_alpha_breakdown.parquet")
inst = pd.read_parquet(processed_root / "institutional_flow.parquet")
daily_price = pd.read_parquet(processed_root / "daily_price.parquet")

if not inst.empty and not daily_price.empty:
    inst_merged = pd.merge(inst, daily_price[["trade_date", "stock_code", "close"]], on=["trade_date", "stock_code"], how="left")
    inst_merged["amount_yi"] = inst_merged["three_party_net_shares"] * inst_merged["close"] / 100000000
    inst_merged = inst_merged.sort_values("trade_date")
    unique_dates = sorted(inst_merged["trade_date"].dropna().unique())
    if unique_dates:
        d5_dates = unique_dates[-5:]
        d20_dates = unique_dates[-20:]
        amount_5d = inst_merged[inst_merged["trade_date"].isin(d5_dates)].groupby("stock_code")["amount_yi"].sum().round(2).to_dict()
        amount_20d = inst_merged[inst_merged["trade_date"].isin(d20_dates)].groupby("stock_code")["amount_yi"].sum().round(2).to_dict()
        stock_alpha["net_5d_yi"] = stock_alpha["stock_code"].map(amount_5d)
        stock_alpha["net_20d_yi"] = stock_alpha["stock_code"].map(amount_20d)

stock_alpha.to_parquet(processed_root / "stock_alpha_breakdown.parquet", index=False)
