from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import math
import pandas as pd


@dataclass
class BacktestResult:
    summary: dict[str, Any]
    daily_returns: pd.DataFrame
    positions: pd.DataFrame


def _next_day_close(df: pd.DataFrame) -> pd.DataFrame:
    # 以 stock_code 分群，將下一筆 close 當作隔日報酬
    df = df.sort_values(["stock_code", "trade_date"]).copy()
    df["next_close"] = df.groupby("stock_code")["close"].shift(-1)
    df["next_date"] = df.groupby("stock_code")["trade_date"].shift(-1)
    return df


def run_alpha_long_only(
    daily_price: pd.DataFrame,
    stock_alpha: pd.DataFrame,
    *,
    top_n: int = 20,
    initial_cash: float = 100_000.0,
) -> BacktestResult:
    if daily_price.empty or stock_alpha.empty:
        return BacktestResult(
            summary={"status": "empty"},
            daily_returns=pd.DataFrame(),
            positions=pd.DataFrame(),
        )

    signal = stock_alpha.dropna(subset=["stock_alpha_score"]).copy()
    signal = signal.sort_values(["trade_date", "stock_alpha_score"], ascending=[True, False])
    signal = signal.groupby("trade_date").head(top_n).copy()
    signal["trade_date"] = pd.to_datetime(signal["trade_date"])
    if "close" in signal.columns:
        signal = signal.drop(columns=["close"])

    prices = daily_price[["trade_date", "market", "stock_code", "close"]].copy()
    prices["trade_date"] = pd.to_datetime(prices["trade_date"])

    joined = signal.merge(prices, on=["trade_date", "market", "stock_code"], how="left")
    joined = _next_day_close(joined)
    joined["return"] = (joined["next_close"] - joined["close"]) / joined["close"]
    joined = joined.dropna(subset=["return"])

    daily = (
        joined.groupby("trade_date")["return"]
        .mean()
        .reset_index()
        .rename(columns={"return": "daily_return"})
    )
    if daily.empty:
        return BacktestResult(
            summary={"status": "no_next_day"},
            daily_returns=daily,
            positions=signal,
        )

    daily["equity"] = (1 + daily["daily_return"]).cumprod() * initial_cash
    summary = {
        "status": "ok",
        "initial_cash": initial_cash,
        "final_equity": float(daily["equity"].iloc[-1]),
        "total_return": float(daily["equity"].iloc[-1] / initial_cash - 1),
        "trading_days": int(daily.shape[0]),
        "hold_top_n": top_n,
    }
    return BacktestResult(summary=summary, daily_returns=daily, positions=signal)


def _max_drawdown(returns: pd.Series) -> float:
    if returns.empty:
        return float("nan")
    equity = (1 + pd.to_numeric(returns, errors="coerce").fillna(0.0)).cumprod()
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    return float(drawdown.min())


def _sharpe_ratio(returns: pd.Series) -> float:
    clean = pd.to_numeric(returns, errors="coerce").dropna()
    if clean.empty or float(clean.std(ddof=0)) == 0.0:
        return float("nan")
    return float(clean.mean() / clean.std(ddof=0) * math.sqrt(252))


def _benchmark_return_from_prices(prices: pd.DataFrame, code: str) -> float:
    if prices.empty or "stock_code" not in prices.columns:
        return float("nan")
    bench = prices[prices["stock_code"].astype(str) == code].copy()
    if bench.shape[0] < 2:
        return float("nan")
    bench["trade_date"] = pd.to_datetime(bench["trade_date"], errors="coerce")
    bench = bench.sort_values("trade_date")
    if bench["trade_date"].nunique() < 2:
        return float("nan")
    first = pd.to_numeric(bench["close"], errors="coerce").iloc[0]
    last = pd.to_numeric(bench["close"], errors="coerce").iloc[-1]
    if pd.isna(first) or first == 0 or pd.isna(last):
        return float("nan")
    return float(last / first - 1.0)


def _benchmark_return_from_index(index_df: pd.DataFrame) -> float:
    if index_df.empty:
        return float("nan")
    idx = index_df.copy()
    if "index_name" in idx.columns:
        preferred = idx[idx["index_name"].astype(str).eq("發行量加權股價指數")]
        if preferred.empty:
            preferred = idx[idx["index_name"].astype(str).str.contains("TAIEX|加權", regex=True, na=False)]
        idx = preferred
    if idx.shape[0] < 2:
        return float("nan")
    idx["trade_date"] = pd.to_datetime(idx["trade_date"], errors="coerce")
    idx = idx.sort_values("trade_date").drop_duplicates("trade_date", keep="first")
    if idx["trade_date"].nunique() < 2:
        return float("nan")
    first = pd.to_numeric(idx["close"], errors="coerce").iloc[0]
    last = pd.to_numeric(idx["close"], errors="coerce").iloc[-1]
    if pd.isna(first) or first == 0 or pd.isna(last):
        return float("nan")
    return float(last / first - 1.0)


def run_recommendation_backtests(
    daily_price: pd.DataFrame,
    stock_scores: pd.DataFrame,
    index_df: pd.DataFrame | None = None,
    *,
    top_ns: tuple[int, ...] = (10, 20),
    lookback_days: int = 252,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if daily_price.empty or stock_scores.empty:
        return pd.DataFrame(
            [
                {
                    "model": "Alpha candidates",
                    "top_n": top_n,
                    "status": "empty",
                    "lookback_days": lookback_days,
                    "trading_days": 0,
                    "cumulative_return": pd.NA,
                    "win_rate": pd.NA,
                    "max_drawdown": pd.NA,
                    "sharpe_ratio": pd.NA,
                    "benchmark_0050_return": pd.NA,
                    "benchmark_taiex_return": pd.NA,
                }
                for top_n in top_ns
            ]
        )

    prices = daily_price[["trade_date", "market", "stock_code", "close"]].copy()
    prices["trade_date"] = pd.to_datetime(prices["trade_date"], errors="coerce")
    prices["stock_code"] = prices["stock_code"].astype(str)
    prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
    prices = prices.dropna(subset=["trade_date", "stock_code", "close"])

    score_col = "alpha_score_total" if "alpha_score_total" in stock_scores.columns else "stock_alpha_score"
    scores = stock_scores.copy()
    scores["trade_date"] = pd.to_datetime(scores["trade_date"], errors="coerce")
    scores["stock_code"] = scores["stock_code"].astype(str)
    scores[score_col] = pd.to_numeric(scores[score_col], errors="coerce")
    scores = scores.dropna(subset=["trade_date", "stock_code", score_col])
    if "is_excluded" in scores.columns:
        scores = scores[~scores["is_excluded"].astype(bool)].copy()

    latest_score_date = scores["trade_date"].max() if not scores.empty else pd.NaT
    if pd.notna(latest_score_date):
        cutoff = latest_score_date - pd.Timedelta(days=int(lookback_days * 1.6))
        scores = scores[scores["trade_date"] >= cutoff].copy()
        prices = prices[prices["trade_date"] >= cutoff].copy()

    benchmark_0050 = _benchmark_return_from_prices(prices, "0050")
    benchmark_taiex = _benchmark_return_from_index(index_df if index_df is not None else pd.DataFrame())

    price_next = prices.sort_values(["market", "stock_code", "trade_date"]).copy()
    price_next["next_close"] = price_next.groupby(["market", "stock_code"])["close"].shift(-1)
    price_next["next_date"] = price_next.groupby(["market", "stock_code"])["trade_date"].shift(-1)

    for top_n in top_ns:
        if prices["trade_date"].nunique() < 2 or scores.empty:
            rows.append(
                {
                    "model": "Alpha candidates",
                    "top_n": top_n,
                    "status": "insufficient_history",
                    "lookback_days": lookback_days,
                    "trading_days": 0,
                    "cumulative_return": pd.NA,
                    "win_rate": pd.NA,
                    "max_drawdown": pd.NA,
                    "sharpe_ratio": pd.NA,
                    "benchmark_0050_return": benchmark_0050,
                    "benchmark_taiex_return": benchmark_taiex,
                }
            )
            continue

        signal = scores.sort_values(["trade_date", score_col], ascending=[True, False])
        signal = signal.groupby("trade_date").head(top_n).copy()
        signal = signal[["trade_date", "market", "stock_code", score_col]]
        joined = signal.merge(
            price_next[["trade_date", "market", "stock_code", "close", "next_close", "next_date"]],
            on=["trade_date", "market", "stock_code"],
            how="left",
        )
        joined["return"] = (joined["next_close"] - joined["close"]) / joined["close"]
        joined = joined.dropna(subset=["return"])
        daily = joined.groupby("trade_date", dropna=False)["return"].mean().sort_index()

        if daily.empty:
            rows.append(
                {
                    "model": "Alpha candidates",
                    "top_n": top_n,
                    "status": "insufficient_history",
                    "lookback_days": lookback_days,
                    "trading_days": 0,
                    "cumulative_return": pd.NA,
                    "win_rate": pd.NA,
                    "max_drawdown": pd.NA,
                    "sharpe_ratio": pd.NA,
                    "benchmark_0050_return": benchmark_0050,
                    "benchmark_taiex_return": benchmark_taiex,
                }
            )
            continue

        cumulative = float((1 + daily).prod() - 1.0)
        rows.append(
            {
                "model": "Alpha candidates",
                "top_n": top_n,
                "status": "ok",
                "lookback_days": lookback_days,
                "trading_days": int(daily.shape[0]),
                "cumulative_return": cumulative,
                "win_rate": float((daily > 0).mean()),
                "max_drawdown": _max_drawdown(daily),
                "sharpe_ratio": _sharpe_ratio(daily),
                "benchmark_0050_return": benchmark_0050,
                "benchmark_taiex_return": benchmark_taiex,
            }
        )

    return pd.DataFrame(rows)
