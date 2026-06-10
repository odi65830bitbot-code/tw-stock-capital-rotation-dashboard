from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


def compute_stock_alpha(
    daily_price: pd.DataFrame,
    institutional_flow: pd.DataFrame,
    sector_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if daily_price.empty:
        return pd.DataFrame()

    base_cols = [
        "trade_date",
        "market",
        "stock_code",
        "stock_name",
        "open",
        "high",
        "low",
        "trade_volume",
        "trade_value_twd",
        "close",
        "change",
    ]
    base = daily_price[[c for c in base_cols if c in daily_price.columns]].copy()

    if institutional_flow.empty:
        df = base
        df["three_party_net_shares"] = pd.NA
    else:
        flow_cols = [
            "trade_date",
            "market",
            "stock_code",
            "stock_name",
            "foreign_net_shares",
            "dealer_net_shares",
            "trustee_net_shares",
            "three_party_net_shares",
            "foreign_net_shares_dealer",
            "foreign_buy_shares",
            "foreign_sell_shares",
            "rank",
        ]
        flow = institutional_flow[[c for c in flow_cols if c in institutional_flow.columns]].copy()
        df = pd.merge(
            base,
            flow,
            on=["trade_date", "market", "stock_code"],
            how="left",
            suffixes=("", "_flow"),
        )
        if "stock_name_flow" in df.columns:
            df["stock_name"] = df["stock_name"].where(df["stock_name"].notna(), df["stock_name_flow"])
            df = df.drop(columns=["stock_name_flow"])

    if "three_party_net_shares" not in df.columns:
        df["three_party_net_shares"] = pd.NA
    df["three_party_net_shares"] = pd.to_numeric(df["three_party_net_shares"], errors="coerce").astype("float64")
    if "trade_volume" in df.columns:
        df["trade_volume"] = pd.to_numeric(df["trade_volume"], errors="coerce").astype("float64")
    df["has_institutional_flow"] = df["three_party_net_shares"].notna()
    df["flow_abs"] = df["three_party_net_shares"].abs()
    volume = df["trade_volume"].where(df["trade_volume"] != 0)
    df["flow_rate"] = df["flow_abs"] / volume
    df["stock_alpha_score"] = df["flow_rate"].fillna(0.0).astype("float64") * 10000

    if sector_df is not None and not sector_df.empty and "stock_code" in df.columns and "industry" in sector_df.columns:
        sector_map = sector_df.set_index("stock_code")["industry"].to_dict()
        df["industry"] = df["stock_code"].map(sector_map).fillna("UNKNOWN")
    elif "industry" not in df.columns:
        df["industry"] = "UNKNOWN"

    return df


def compute_sector_alpha(stock_alpha: pd.DataFrame) -> pd.DataFrame:
    if stock_alpha.empty:
        return pd.DataFrame()
    return (
        stock_alpha.groupby(["trade_date", "market", "industry"], dropna=False)["stock_alpha_score"]
        .mean()
        .reset_index()
        .rename(columns={"stock_alpha_score": "sector_alpha_score"})
    )


def save_scores(stock_alpha: pd.DataFrame, sector_alpha: pd.DataFrame, output_root: Path) -> Dict[str, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    stock_path = output_root / "stock_alpha.parquet"
    sector_path = output_root / "sector_alpha.parquet"
    if not stock_alpha.empty:
        stock_alpha.to_parquet(stock_path, index=False)
    if not sector_alpha.empty:
        sector_alpha.to_parquet(sector_path, index=False)
    return {"stock_alpha": stock_path, "sector_alpha": sector_path}
