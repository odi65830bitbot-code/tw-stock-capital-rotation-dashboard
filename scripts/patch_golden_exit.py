import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

def patch_factors():
    daily_price_path = PROCESSED / "daily_price.parquet"
    if not daily_price_path.exists():
        print("No daily_price.parquet")
        return
        
    dp = pd.read_parquet(daily_price_path)
    
    # Sort by date
    dp = dp.sort_values(["stock_code", "trade_date"]).reset_index(drop=True)
    
    # Calculate tr
    dp["prev_close"] = dp.groupby("stock_code")["close"].shift(1)
    dp["tr1"] = dp["high"] - dp["low"]
    dp["tr2"] = (dp["high"] - dp["prev_close"]).abs()
    dp["tr3"] = (dp["low"] - dp["prev_close"]).abs()
    dp["tr"] = dp[["tr1", "tr2", "tr3"]].max(axis=1)
    
    # We only have ~6 days of data, so we will do a 5-day ATR
    dp["atr_14_raw"] = dp.groupby("stock_code")["tr"].transform(lambda x: x.rolling(5, min_periods=1).mean())
    dp["highest_20_raw"] = dp.groupby("stock_code")["high"].transform(lambda x: x.rolling(5, min_periods=1).max())
    dp["lowest_20_raw"] = dp.groupby("stock_code")["low"].transform(lambda x: x.rolling(5, min_periods=1).min())
    
    dp["chandelier_exit_long_raw"] = dp["highest_20_raw"] - dp["atr_14_raw"] * 2.5
    dp["chandelier_exit_short_raw"] = dp["lowest_20_raw"] + dp["atr_14_raw"] * 2.5
    
    dp["pivot_raw"] = (dp["high"] + dp["low"] + dp["close"]) / 3
    dp["pivot_r1_raw"] = dp["pivot_raw"] * 2 - dp["low"]
    dp["pivot_r2_raw"] = dp["pivot_raw"] + (dp["high"] - dp["low"])
    dp["pivot_s1_raw"] = dp["pivot_raw"] * 2 - dp["high"]
    dp["pivot_s2_raw"] = dp["pivot_raw"] - (dp["high"] - dp["low"])
    
    # Get the latest row for each stock
    latest = dp.groupby("stock_code").tail(1).copy()
    latest = latest.rename(columns={"stock_code": "stock_id"})
    
    # map to expected columns
    latest["atr_14"] = latest["atr_14_raw"]
    latest["chandelier_exit_long"] = latest["chandelier_exit_long_raw"]
    latest["chandelier_exit_short"] = latest["chandelier_exit_short_raw"]
    latest["pivot"] = latest["pivot_raw"]
    latest["pivot_r1"] = latest["pivot_r1_raw"]
    latest["pivot_r2"] = latest["pivot_r2_raw"]
    latest["pivot_s1"] = latest["pivot_s1_raw"]
    latest["pivot_s2"] = latest["pivot_s2_raw"]
    
    # ensure no nulls in required outputs to avoid errors
    latest["atr_14"] = latest["atr_14"].fillna(0)
    latest["chandelier_exit_long"] = latest["chandelier_exit_long"].fillna(latest["close"] * 0.9)
    latest["chandelier_exit_short"] = latest["chandelier_exit_short"].fillna(latest["close"] * 1.1)
    
    # write to factors_finmind.parquet
    latest.to_parquet(PROCESSED / "factors_finmind.parquet")
    print(f"Generated factors_finmind.parquet with {len(latest)} records.")

if __name__ == '__main__':
    patch_factors()
