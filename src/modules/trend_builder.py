from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.trading_calendar import latest_complete_trade_date


DEFAULT_TREND_TOP_N = 100


def _latest_date(df: pd.DataFrame) -> pd.Timestamp | None:
    if df.empty or "trade_date" not in df.columns:
        return None
    dates = pd.to_datetime(df["trade_date"], errors="coerce").dropna()
    return dates.max() if not dates.empty else None


def _json_ready(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    out = df.copy()
    if "trade_date" in out.columns:
        out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return [
        {str(k): _json_ready(v) for k, v in row.items()}
        for row in out.replace({pd.NA: None}).to_dict(orient="records")
    ]


def top_recommendation_codes(
    recommendations: pd.DataFrame,
    *,
    top_n: int = DEFAULT_TREND_TOP_N,
    as_of_date: pd.Timestamp | None = None,
) -> list[str]:
    if recommendations.empty:
        return []
    rec = recommendations.copy()
    rec["trade_date"] = pd.to_datetime(rec["trade_date"], errors="coerce")
    latest = pd.to_datetime(as_of_date) if as_of_date is not None else rec["trade_date"].max()
    rec = rec[rec["trade_date"] == latest].copy()
    rec = rec.sort_values(["overall_rank", "alpha_score_total"], ascending=[True, False], na_position="last")
    return rec["stock_code"].astype(str).drop_duplicates().head(top_n).tolist()


def _latest_price_universe_codes(
    daily_price: pd.DataFrame,
    recommendations: pd.DataFrame,
    *,
    top_n: int = DEFAULT_TREND_TOP_N,
    as_of_date: pd.Timestamp | None = None,
) -> list[str]:
    if top_n <= 0:
        return []
    if daily_price.empty or "stock_code" not in daily_price.columns or "trade_date" not in daily_price.columns:
        return top_recommendation_codes(recommendations, top_n=top_n, as_of_date=as_of_date)

    price = daily_price.copy()
    price["trade_date"] = pd.to_datetime(price["trade_date"], errors="coerce")
    latest = pd.to_datetime(as_of_date) if as_of_date is not None else price["trade_date"].max()
    latest_price = price[price["trade_date"] == latest].copy()
    if latest_price.empty:
        return []

    universe = latest_price["stock_code"].astype(str).drop_duplicates().tolist()
    recommended = top_recommendation_codes(recommendations, top_n=top_n, as_of_date=latest)
    ordered = [code for code in recommended if code in set(universe)]
    ordered.extend(code for code in universe if code not in set(ordered))
    return ordered[:top_n]


def build_stock_trend(
    stock_id: str,
    daily_price: pd.DataFrame,
    institutional_flow: pd.DataFrame,
    stock_alpha_breakdown: pd.DataFrame,
    sector_alpha: pd.DataFrame,
    recommendations: pd.DataFrame,
    *,
    max_days: int = 252,
) -> dict[str, Any]:
    stock_id = str(stock_id)
    price = daily_price[daily_price["stock_code"].astype(str) == stock_id].copy() if not daily_price.empty else pd.DataFrame()
    flow = institutional_flow[institutional_flow["stock_code"].astype(str) == stock_id].copy() if not institutional_flow.empty else pd.DataFrame()
    alpha = stock_alpha_breakdown[stock_alpha_breakdown["stock_code"].astype(str) == stock_id].copy() if not stock_alpha_breakdown.empty else pd.DataFrame()

    for df in (price, flow, alpha):
        if not df.empty and "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")

    if not price.empty:
        price = price.sort_values("trade_date").tail(max_days)
        price["ma5"] = pd.to_numeric(price["close"], errors="coerce").rolling(5, min_periods=1).mean()
        price["ma20"] = pd.to_numeric(price["close"], errors="coerce").rolling(20, min_periods=1).mean()
        price["ma60"] = pd.to_numeric(price["close"], errors="coerce").rolling(60, min_periods=1).mean()
        price["trade_value_ma20"] = pd.to_numeric(price["trade_value_twd"], errors="coerce").rolling(20, min_periods=1).mean()
        price["trade_value_multiple"] = (
            pd.to_numeric(price["trade_value_twd"], errors="coerce")
            / price["trade_value_ma20"].where(price["trade_value_ma20"] > 0)
        )

    if not flow.empty:
        flow = flow.sort_values("trade_date").tail(max_days)
        for col, prefix in [
            ("foreign_net_shares", "foreign"),
            ("trustee_net_shares", "trust"),
            ("dealer_net_shares", "dealer"),
        ]:
            values = pd.to_numeric(flow[col], errors="coerce") if col in flow.columns else pd.Series(0, index=flow.index)
            flow[f"{prefix}_5d"] = values.rolling(5, min_periods=1).sum()
            flow[f"{prefix}_20d"] = values.rolling(20, min_periods=1).sum()

    if not alpha.empty:
        alpha = alpha.sort_values("trade_date").tail(max_days)
        sector_key = alpha[["trade_date", "market", "industry"]].dropna().drop_duplicates()
        if not sector_key.empty and not sector_alpha.empty:
            sector = sector_alpha.copy()
            sector["trade_date"] = pd.to_datetime(sector["trade_date"], errors="coerce")
            alpha = alpha.merge(
                sector[["trade_date", "market", "industry", "sector_alpha_score"]],
                on=["trade_date", "market", "industry"],
                how="left",
                suffixes=("", "_trend"),
            )

    rec = recommendations[recommendations["stock_code"].astype(str) == stock_id].copy() if not recommendations.empty else pd.DataFrame()
    if not rec.empty:
        rec["trade_date"] = pd.to_datetime(rec["trade_date"], errors="coerce")
        rec = rec.sort_values("trade_date")

    first_rec_date = rec["trade_date"].min() if not rec.empty else pd.NaT
    latest_rec_date = _latest_date(recommendations)
    latest_price = pd.to_numeric(price["close"], errors="coerce").iloc[-1] if not price.empty else pd.NA
    rec_close = pd.NA
    post_return = pd.NA
    post_max_drawdown = pd.NA
    post_max_gain = pd.NA
    if pd.notna(first_rec_date) and not price.empty:
        post = price[price["trade_date"] >= first_rec_date].copy()
        if not post.empty:
            rec_close = pd.to_numeric(post["close"], errors="coerce").iloc[0]
            if pd.notna(rec_close) and rec_close != 0:
                closes = pd.to_numeric(post["close"], errors="coerce")
                post_return = latest_price / rec_close - 1
                post_max_gain = closes.max() / rec_close - 1
                equity = closes / rec_close
                post_max_drawdown = float((equity / equity.cummax() - 1).min())

    latest_alpha = alpha.iloc[-1] if not alpha.empty else {}
    payload = {
        "stock_id": stock_id,
        "stock_name": str(price["stock_name"].iloc[-1]) if not price.empty and "stock_name" in price.columns else "",
        "market": str(price["market"].iloc[-1]) if not price.empty and "market" in price.columns else "",
        "industry": str(latest_alpha.get("industry", "")) if isinstance(latest_alpha, pd.Series) else "",
        "generated_at": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "price": _records(price[["trade_date", "close", "ma5", "ma20", "ma60"]] if not price.empty else pd.DataFrame()),
        "trade_value": _records(
            price[["trade_date", "trade_value_twd", "trade_value_ma20", "trade_value_multiple"]]
            if not price.empty
            else pd.DataFrame()
        ),
        "institutional_flow": _records(
            flow[
                [
                    "trade_date",
                    "foreign_net_shares",
                    "trustee_net_shares",
                    "dealer_net_shares",
                    "foreign_5d",
                    "foreign_20d",
                    "trust_5d",
                    "trust_20d",
                    "dealer_5d",
                    "dealer_20d",
                ]
            ]
            if not flow.empty
            else pd.DataFrame()
        ),
        "alpha": _records(
            alpha[
                [
                    "trade_date",
                    "stock_alpha_score",
                    "alpha_score_total",
                    "sector_alpha_score",
                    "main_buy_component",
                    "risk_penalty",
                ]
            ]
            if not alpha.empty
            else pd.DataFrame()
        ),
        "recommendation": {
            "first_recommend_date": _json_ready(first_rec_date),
            "recommend_close": _json_ready(rec_close),
            "current_price": _json_ready(latest_price),
            "post_recommend_return": _json_ready(post_return),
            "post_recommend_max_drawdown": _json_ready(post_max_drawdown),
            "post_recommend_max_gain": _json_ready(post_max_gain),
            "still_recommended": bool(
                pd.notna(latest_rec_date)
                and not rec.empty
                and (rec["trade_date"] == latest_rec_date).any()
            ),
        },
    }
    return payload


def write_top_recommendation_trends(
    *,
    processed_root: Path,
    public_root: Path,
    top_n: int = DEFAULT_TREND_TOP_N,
) -> list[Path]:
    processed_root = Path(processed_root)
    public_root = Path(public_root)
    daily_price = pd.read_parquet(processed_root / "daily_price.parquet")
    institutional_flow = pd.read_parquet(processed_root / "institutional_flow.parquet")
    stock_alpha_breakdown = pd.read_parquet(processed_root / "stock_alpha_breakdown.parquet")
    sector_alpha = pd.read_parquet(processed_root / "sector_alpha.parquet")
    recommendations = pd.read_parquet(processed_root / "recommendations.parquet")

    trend_dir = public_root / "data" / "trends"
    trend_dir.mkdir(parents=True, exist_ok=True)
    for stale in trend_dir.glob("*.json"):
        stale.unlink()
    written: list[Path] = []
    as_of_date = latest_complete_trade_date(daily_price)
    for stock_id in _latest_price_universe_codes(daily_price, recommendations, top_n=top_n, as_of_date=as_of_date):
        payload = build_stock_trend(
            stock_id,
            daily_price,
            institutional_flow,
            stock_alpha_breakdown,
            sector_alpha,
            recommendations,
        )
        path = trend_dir / f"{stock_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(path)
    return written
