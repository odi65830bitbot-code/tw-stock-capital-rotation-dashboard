from __future__ import annotations

import pandas as pd


def latest_complete_trade_date(
    daily_price: pd.DataFrame,
    *,
    market_col: str = "market",
    date_col: str = "trade_date",
    required_markets: tuple[str, ...] = ("TWSE", "TPEX"),
) -> pd.Timestamp | None:
    if daily_price.empty or date_col not in daily_price.columns or market_col not in daily_price.columns:
        return None
    df = daily_price[[date_col, market_col]].copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col, market_col])
    if df.empty:
        return None
    required = set(required_markets)
    grouped = df.groupby(date_col)[market_col].agg(lambda s: set(s.dropna().astype(str)))
    complete_dates = [date for date, markets in grouped.items() if required.issubset(markets)]
    if complete_dates:
        return max(complete_dates)
    return df[date_col].max()
