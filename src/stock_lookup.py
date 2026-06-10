from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class StockLookupResult:
    stock_id: str
    stock_name: str
    market: str
    sector: str
    match_rank: int


def build_stock_universe(
    daily_price: pd.DataFrame,
    sector_classification: pd.DataFrame | None = None,
    stock_alpha_breakdown: pd.DataFrame | None = None,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for df in (daily_price, stock_alpha_breakdown, sector_classification):
        if df is None or df.empty:
            continue
        cols = [c for c in ["market", "stock_code", "stock_name", "industry"] if c in df.columns]
        if {"market", "stock_code"}.issubset(cols):
            frames.append(df[cols].copy())
    if not frames:
        return pd.DataFrame(columns=["stock_code", "stock_name", "market", "industry"])

    universe = pd.concat(frames, ignore_index=True)
    universe["stock_code"] = universe["stock_code"].astype(str).str.strip()
    universe["stock_name"] = universe.get("stock_name", pd.Series("", index=universe.index)).fillna("").astype(str).str.strip()
    universe["industry"] = universe.get("industry", pd.Series("UNKNOWN", index=universe.index)).fillna("UNKNOWN").astype(str)
    universe = universe[universe["stock_code"].ne("")]
    universe = (
        universe.sort_values(["stock_code", "stock_name", "industry"])
        .drop_duplicates(["market", "stock_code"], keep="last")
        .reset_index(drop=True)
    )
    return universe


def find_stock_matches(
    query: str,
    daily_price: pd.DataFrame,
    sector_classification: pd.DataFrame | None = None,
    stock_alpha_breakdown: pd.DataFrame | None = None,
    *,
    limit: int = 20,
) -> list[StockLookupResult]:
    q = str(query or "").strip().lower()
    if not q:
        return []

    universe = build_stock_universe(daily_price, sector_classification, stock_alpha_breakdown)
    if universe.empty:
        return []

    code = universe["stock_code"].astype(str).str.lower()
    name = universe["stock_name"].astype(str).str.lower()
    industry = universe["industry"].astype(str).str.lower()
    mask = code.str.contains(q, regex=False) | name.str.contains(q, regex=False) | industry.str.contains(q, regex=False)
    matches = universe[mask].copy()
    if matches.empty:
        return []

    matches["_match_rank"] = 9
    matches.loc[code[mask].eq(q).values, "_match_rank"] = 0
    matches.loc[name[mask].eq(q).values & matches["_match_rank"].eq(9), "_match_rank"] = 1
    matches.loc[code[mask].str.startswith(q).values & matches["_match_rank"].eq(9), "_match_rank"] = 2
    matches.loc[name[mask].str.contains(q, regex=False).values & matches["_match_rank"].eq(9), "_match_rank"] = 3
    matches.loc[industry[mask].str.contains(q, regex=False).values & matches["_match_rank"].eq(9), "_match_rank"] = 4
    matches = matches.sort_values(["_match_rank", "market", "stock_code"]).head(limit)

    return [
        StockLookupResult(
            stock_id=str(row.get("stock_code", "")),
            stock_name=str(row.get("stock_name", "")),
            market=str(row.get("market", "")),
            sector=str(row.get("industry", "UNKNOWN")),
            match_rank=int(row.get("_match_rank", 9)),
        )
        for _, row in matches.iterrows()
    ]


def get_exact_or_best_match(
    query: str,
    daily_price: pd.DataFrame,
    sector_classification: pd.DataFrame | None = None,
    stock_alpha_breakdown: pd.DataFrame | None = None,
) -> StockLookupResult | None:
    matches = find_stock_matches(query, daily_price, sector_classification, stock_alpha_breakdown, limit=1)
    return matches[0] if matches else None
