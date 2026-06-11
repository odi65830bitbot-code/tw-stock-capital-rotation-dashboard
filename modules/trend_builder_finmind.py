from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_TREND_TOP_N = 100


def _date_col(df: pd.DataFrame) -> str:
    return "trade_date" if "trade_date" in df.columns else "date"


def _stock_col(df: pd.DataFrame) -> str:
    return "stock_code" if "stock_code" in df.columns else "stock_id"


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    out = df.copy()
    if "trade_date" in out.columns:
        out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return out.replace({pd.NA: None}).to_dict(orient="records")


def _stock_filter(df: pd.DataFrame, stock_id: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    out = df.copy()
    out["trade_date"] = pd.to_datetime(out[_date_col(out)], errors="coerce")
    out["stock_id"] = out[_stock_col(out)].astype(str)
    return out[out["stock_id"] == str(stock_id)].sort_values("trade_date")


def _latest_price_universe_stock_ids(
    price: pd.DataFrame,
    recommendations: pd.DataFrame,
    *,
    top_n: int = DEFAULT_TREND_TOP_N,
) -> list[str]:
    if top_n <= 0:
        return []
    if price.empty:
        return recommendations.get("stock_id", pd.Series(dtype=str)).astype(str).drop_duplicates().head(top_n).tolist()

    out = price.copy()
    out["trade_date"] = pd.to_datetime(out[_date_col(out)], errors="coerce")
    out["stock_id"] = out[_stock_col(out)].astype(str)
    latest = out["trade_date"].max()
    latest_price = out[out["trade_date"] == latest].copy()
    if latest_price.empty:
        return []

    universe = latest_price["stock_id"].drop_duplicates().tolist()
    if recommendations.empty or "stock_id" not in recommendations.columns:
        return universe[:top_n]

    recs = recommendations.copy()
    sort_cols = [col for col in ["stock_alpha_v3", "confidence_score"] if col in recs.columns]
    if sort_cols:
        recs = recs.sort_values(sort_cols, ascending=[False] * len(sort_cols), na_position="last")
    universe_set = set(universe)
    ordered = [stock_id for stock_id in recs["stock_id"].astype(str).drop_duplicates().tolist() if stock_id in universe_set]
    ordered_set = set(ordered)
    ordered.extend(stock_id for stock_id in universe if stock_id not in ordered_set)
    return ordered[:top_n]


def build_finmind_stock_trend(
    stock_id: str,
    *,
    price: pd.DataFrame,
    institutional: pd.DataFrame,
    margin: pd.DataFrame,
    revenue: pd.DataFrame,
    alpha_v3: pd.DataFrame,
    recommendations: pd.DataFrame,
    max_days: int = 252,
) -> dict[str, Any]:
    p = _stock_filter(price, stock_id).tail(max_days)
    if not p.empty:
        for source, target in [("Trading_money", "trade_value"), ("trade_value_twd", "trade_value")]:
            if source in p.columns and target not in p.columns:
                p[target] = p[source]
        p["close"] = pd.to_numeric(p["close"], errors="coerce")
        p["trade_value"] = pd.to_numeric(p.get("trade_value", pd.NA), errors="coerce")
        p["ma5"] = p["close"].rolling(5, min_periods=1).mean()
        p["ma20"] = p["close"].rolling(20, min_periods=1).mean()
        p["ma60"] = p["close"].rolling(60, min_periods=1).mean()
        p["trade_value_ma20"] = p["trade_value"].rolling(20, min_periods=1).mean()

    inst = _stock_filter(institutional, stock_id).tail(max_days)
    if not inst.empty:
        name = inst.get("name", "").astype(str)
        inst["net"] = pd.to_numeric(inst.get("buy", 0), errors="coerce") - pd.to_numeric(inst.get("sell", 0), errors="coerce")
        daily = pd.DataFrame({"trade_date": sorted(inst["trade_date"].dropna().unique())})
        for pattern, col in [("Foreign|外資", "foreign"), ("Investment|Trust|投信", "investment_trust")]:
            subset = inst[name.str.contains(pattern, case=False, regex=True, na=False)]
            agg = subset.groupby("trade_date")["net"].sum().reset_index(name=f"{col}_buy_1d")
            daily = daily.merge(agg, on="trade_date", how="left")
            daily[f"{col}_buy_5d"] = daily[f"{col}_buy_1d"].fillna(0).rolling(5, min_periods=1).sum()
            daily[f"{col}_buy_20d"] = daily[f"{col}_buy_1d"].fillna(0).rolling(20, min_periods=1).sum()
        inst = daily

    m = _stock_filter(margin, stock_id).tail(max_days)
    if not m.empty:
        for source, target in [
            ("MarginPurchaseTodayBalance", "margin_balance"),
            ("ShortSaleTodayBalance", "short_balance"),
        ]:
            if source in m.columns and target not in m.columns:
                m[target] = m[source]

    rev = _stock_filter(revenue, stock_id).tail(24)
    if not rev.empty:
        rev["revenue"] = pd.to_numeric(rev.get("revenue", pd.NA), errors="coerce")
        rev["revenue_mom"] = rev["revenue"].pct_change()
        rev["month"] = rev["trade_date"].dt.month
        rev["year"] = rev["trade_date"].dt.year
        yoy = rev[["month", "year", "revenue"]].rename(columns={"revenue": "prev_year_revenue"})
        rev["prev_year"] = rev["year"] - 1
        rev = rev.merge(yoy, left_on=["month", "prev_year"], right_on=["month", "year"], how="left", suffixes=("", "_prev"))
        rev["revenue_yoy"] = (rev["revenue"] - rev["prev_year_revenue"]) / rev["prev_year_revenue"].where(rev["prev_year_revenue"] > 0)

    a = _stock_filter(alpha_v3, stock_id).tail(max_days) if not alpha_v3.empty else pd.DataFrame()
    rec = recommendations[recommendations["stock_id"].astype(str) == str(stock_id)].copy() if not recommendations.empty else pd.DataFrame()
    markers = pd.DataFrame()
    if not rec.empty and "trade_date" in rec.columns:
        rec["trade_date"] = pd.to_datetime(rec["trade_date"], errors="coerce")
        markers = rec[["trade_date", "recommendation_type", "status", "summary_reason"]].dropna(subset=["trade_date"])

    latest = rec.iloc[0] if not rec.empty else {}
    return {
        "stock_id": str(stock_id),
        "stock_name": str(latest.get("stock_name", "")) if isinstance(latest, pd.Series) else "",
        "market": str(latest.get("market", "")) if isinstance(latest, pd.Series) else "",
        "sector": str(latest.get("sector", "")) if isinstance(latest, pd.Series) else "",
        "generated_at": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "price": _records(p[["trade_date", "close", "ma5", "ma20", "ma60"]] if not p.empty else pd.DataFrame()),
        "trade_value": _records(p[["trade_date", "trade_value", "trade_value_ma20"]] if not p.empty else pd.DataFrame()),
        "institutional": _records(inst),
        "margin": _records(m[[c for c in ["trade_date", "margin_balance", "short_balance"] if c in m.columns]] if not m.empty else pd.DataFrame()),
        "revenue": _records(rev[[c for c in ["trade_date", "revenue", "revenue_yoy", "revenue_mom"] if c in rev.columns]] if not rev.empty else pd.DataFrame()),
        "alpha": _records(
            a[
                [
                    c
                    for c in [
                        "trade_date",
                        "stock_alpha_v3",
                        "sector_alpha",
                        "main_force_proxy",
                        "risk_penalty_total",
                        "confidence_score",
                    ]
                    if c in a.columns
                ]
            ]
            if not a.empty
            else pd.DataFrame()
        ),
        "recommendation_event_marker": _records(markers),
        "recommendation": latest.to_dict() if isinstance(latest, pd.Series) else {},
    }


def write_finmind_recommendation_trends(
    *,
    processed_root: Path,
    public_root: Path,
    top_n: int = DEFAULT_TREND_TOP_N,
) -> list[Path]:
    processed_root = Path(processed_root)
    public_root = Path(public_root)
    recommendations = pd.read_parquet(processed_root / "recommendations_v3.parquet")
    price = pd.read_parquet(processed_root / "finmind_price.parquet")
    institutional = pd.read_parquet(processed_root / "finmind_institutional.parquet")
    margin = pd.read_parquet(processed_root / "finmind_margin.parquet")
    revenue = pd.read_parquet(processed_root / "finmind_revenue.parquet")
    alpha_v3 = pd.read_parquet(processed_root / "stock_alpha_v3.parquet")
    trend_dir = public_root / "data" / "trends"
    trend_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for stock_id in _latest_price_universe_stock_ids(price, recommendations, top_n=top_n):
        payload = build_finmind_stock_trend(
            stock_id,
            price=price,
            institutional=institutional,
            margin=margin,
            revenue=revenue,
            alpha_v3=alpha_v3,
            recommendations=recommendations,
        )
        path = trend_dir / f"{stock_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        paths.append(path)
    return paths
