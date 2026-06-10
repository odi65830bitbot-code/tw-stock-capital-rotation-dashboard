from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


BUY_FEE = 0.001425
SELL_FEE = 0.001425
SELL_TAX = 0.003
DEFAULT_SLIPPAGE = 0.001


def _price_frame(prices: pd.DataFrame) -> pd.DataFrame:
    df = prices.copy()
    if "trade_date" not in df.columns:
        df["trade_date"] = pd.to_datetime(df["date"], errors="coerce")
    else:
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    if "stock_id" not in df.columns and "stock_code" in df.columns:
        df["stock_id"] = df["stock_code"].astype(str)
    df["stock_id"] = df["stock_id"].astype(str)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df.dropna(subset=["trade_date", "stock_id", "close"]).sort_values(["stock_id", "trade_date"])


def _factor_frame(factors: pd.DataFrame) -> pd.DataFrame:
    df = factors.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    if "stock_id" not in df.columns and "stock_code" in df.columns:
        df["stock_id"] = df["stock_code"].astype(str)
    df["stock_id"] = df["stock_id"].astype(str)
    return df.dropna(subset=["trade_date", "stock_id"])


def _with_forward_return(prices: pd.DataFrame) -> pd.DataFrame:
    p = _price_frame(prices)
    p["next_close"] = p.groupby("stock_id")["close"].shift(-1)
    p["next_date"] = p.groupby("stock_id")["trade_date"].shift(-1)
    p["forward_return_1d"] = p["next_close"] / p["close"] - 1
    return p


def _max_drawdown(returns: pd.Series) -> float:
    clean = pd.to_numeric(returns, errors="coerce").fillna(0.0)
    if clean.empty:
        return float("nan")
    equity = (1 + clean).cumprod()
    return float((equity / equity.cummax() - 1).min())


def _sharpe(returns: pd.Series) -> float:
    clean = pd.to_numeric(returns, errors="coerce").dropna()
    if clean.empty or float(clean.std(ddof=0)) == 0:
        return float("nan")
    return float(clean.mean() / clean.std(ddof=0) * math.sqrt(252))


def validate_factor_effectiveness(
    factors: pd.DataFrame,
    prices: pd.DataFrame,
    *,
    factor_cols: list[str] | None = None,
) -> pd.DataFrame:
    if factors.empty or prices.empty:
        return pd.DataFrame()
    f = _factor_frame(factors)
    p = _with_forward_return(prices)
    joined = f.merge(
        p[["trade_date", "stock_id", "close", "next_date", "forward_return_1d"]],
        on=["trade_date", "stock_id"],
        how="inner",
    )
    if joined.empty:
        return pd.DataFrame()
    factor_cols = factor_cols or [
        c
        for c in joined.columns
        if c not in {"trade_date", "market", "stock_id", "stock_name", "close", "next_date", "forward_return_1d"}
        and pd.api.types.is_numeric_dtype(joined[c])
    ]
    rows: list[dict[str, Any]] = []
    for col in factor_cols:
        if col not in joined.columns:
            continue
        sample = joined[[col, "forward_return_1d"]].apply(pd.to_numeric, errors="coerce").dropna()
        if sample.shape[0] < 2:
            ic = float("nan")
            rank_ic = float("nan")
        else:
            ic = float(sample[col].corr(sample["forward_return_1d"]))
            rank_ic = float(sample[col].rank().corr(sample["forward_return_1d"].rank()))
        ranked = joined.dropna(subset=[col, "forward_return_1d"]).copy()
        if ranked.empty:
            top_decile = bottom_decile = spread = float("nan")
        else:
            ranked["bucket"] = pd.qcut(ranked[col].rank(method="first"), q=min(10, ranked.shape[0]), labels=False, duplicates="drop")
            top_decile = float(ranked[ranked["bucket"] == ranked["bucket"].max()]["forward_return_1d"].mean())
            bottom_decile = float(ranked[ranked["bucket"] == ranked["bucket"].min()]["forward_return_1d"].mean())
            spread = top_decile - bottom_decile
        rows.append(
            {
                "factor": col,
                "sample_size": int(sample.shape[0]),
                "ic": ic,
                "rank_ic": rank_ic,
                "top_decile_return": top_decile,
                "bottom_decile_return": bottom_decile,
                "top_minus_bottom": spread,
                "uses_future_data": False,
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out["effectiveness_score"] = (
            pd.to_numeric(out["rank_ic"], errors="coerce").abs().fillna(0) * 60
            + pd.to_numeric(out["top_minus_bottom"], errors="coerce").fillna(0).clip(lower=0) * 400
        ).clip(0, 100)
        out = out.sort_values("effectiveness_score", ascending=False).reset_index(drop=True)
    return out


def run_alpha_v3_backtest(
    prices: pd.DataFrame,
    alpha: pd.DataFrame,
    *,
    top_ns: tuple[int, ...] = (5, 10, 20),
    slippage: float = DEFAULT_SLIPPAGE,
    lookback_months: int = 12,
) -> pd.DataFrame:
    if prices.empty or alpha.empty:
        return pd.DataFrame({"top_n": list(top_ns), "status": ["empty"] * len(top_ns)})
    p = _with_forward_return(prices)
    a = _factor_frame(alpha)
    score_col = "stock_alpha_v3" if "stock_alpha_v3" in a.columns else "alpha_score_total"
    a[score_col] = pd.to_numeric(a[score_col], errors="coerce")
    if "status" in a.columns:
        a = a[~a["status"].astype(str).isin(["避開"])].copy()
    latest = a["trade_date"].max()
    if pd.notna(latest):
        cutoff = latest - pd.DateOffset(months=lookback_months)
        a = a[a["trade_date"] >= cutoff].copy()
        p = p[p["trade_date"] >= cutoff].copy()
    joined_base = a.merge(
        p[["trade_date", "stock_id", "close", "next_close", "next_date", "forward_return_1d"]],
        on=["trade_date", "stock_id"],
        how="inner",
    ).dropna(subset=[score_col, "forward_return_1d"])
    total_cost = BUY_FEE + SELL_FEE + SELL_TAX + float(slippage)
    rows: list[dict[str, Any]] = []
    for top_n in top_ns:
        if joined_base.empty:
            rows.append({"model": "Stock Alpha v3", "top_n": top_n, "status": "insufficient_history"})
            continue
        signal = joined_base.sort_values(["trade_date", score_col], ascending=[True, False])
        signal = signal.groupby("trade_date").head(top_n).copy()
        signal["net_return"] = signal["forward_return_1d"] - total_cost
        daily = signal.groupby("trade_date")["net_return"].mean().sort_index()
        rows.append(
            {
                "model": "Stock Alpha v3",
                "top_n": top_n,
                "status": "ok" if not daily.empty else "insufficient_history",
                "lookback_months": lookback_months,
                "trading_days": int(daily.shape[0]),
                "cumulative_return": float((1 + daily).prod() - 1) if not daily.empty else pd.NA,
                "win_rate": float((daily > 0).mean()) if not daily.empty else pd.NA,
                "avg_return_20d": float(daily.rolling(20, min_periods=1).mean().iloc[-1]) if not daily.empty else pd.NA,
                "max_drawdown": _max_drawdown(daily) if not daily.empty else pd.NA,
                "sharpe_ratio": _sharpe(daily) if not daily.empty else pd.NA,
                "transaction_cost": total_cost,
                "uses_future_data": False,
            }
        )
    return pd.DataFrame(rows)


def write_backtest_outputs(
    *,
    backtest: pd.DataFrame,
    effectiveness: pd.DataFrame,
    public_root: Path = Path("public"),
    report_path: Path = Path("reports/backtest_alpha_v3.md"),
) -> None:
    out_dir = public_root / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "backtest_alpha_v3.json").write_text(
        json.dumps({"records": backtest.to_dict(orient="records")}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    (out_dir / "factor_effectiveness.json").write_text(
        json.dumps({"records": effectiveness.to_dict(orient="records")}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    def _table(df: pd.DataFrame) -> str:
        if df.empty:
            return "No rows."
        try:
            return df.to_markdown(index=False)
        except Exception:
            return df.to_csv(index=False)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Alpha v3 Backtest Report",
        "",
        "本報告僅用於觀察模型驗證，不構成買賣建議。",
        "",
        "## Backtest Summary",
        _table(backtest),
        "",
        "## Factor Effectiveness",
        _table(effectiveness.head(20)),
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
