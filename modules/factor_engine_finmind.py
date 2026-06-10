from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


FACTOR_COLUMNS = (
    "return_5d",
    "return_20d",
    "return_60d",
    "ma5",
    "ma20",
    "ma60",
    "close_above_ma20",
    "close_above_ma60",
    "relative_strength_vs_taiex",
    "relative_strength_vs_sector",
    "volatility_20d",
    "max_drawdown_60d",
    "trade_value_1d",
    "trade_value_ma20",
    "trade_value_ratio_20d",
    "turnover_proxy",
    "liquidity_score",
    "foreign_buy_1d",
    "foreign_buy_5d",
    "foreign_buy_20d",
    "investment_trust_buy_1d",
    "investment_trust_buy_5d",
    "investment_trust_buy_20d",
    "dealer_buy_1d",
    "dealer_buy_5d",
    "dealer_buy_20d",
    "institution_sync_score",
    "institution_accumulation_score",
    "margin_balance_change_1d",
    "margin_balance_change_5d",
    "margin_balance_change_20d",
    "short_balance_change_1d",
    "short_balance_change_5d",
    "margin_overheat_score",
    "short_covering_score",
    "credit_health_score",
    "revenue_yoy",
    "revenue_mom",
    "revenue_3m_yoy",
    "revenue_6m_trend",
    "revenue_acceleration_score",
    "eps_ttm",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "roe",
    "debt_ratio",
    "operating_cash_flow",
    "free_cash_flow_proxy",
    "quality_score",
    "pe_ratio",
    "pb_ratio",
    "dividend_yield",
    "valuation_score",
    "volume_price_sync",
    "institutional_sync",
    "trade_value_abnormal",
    "consecutive_inflow_days",
    "sector_strength",
    "not_overheated_score",
    "main_force_proxy",
    "overheat_penalty",
    "high_volatility_penalty",
    "low_liquidity_penalty",
    "weak_financial_penalty",
    "margin_overheat_penalty",
    "risk_penalty_total",
)


def _num(series: pd.Series | Any, index: pd.Index | None = None) -> pd.Series:
    if isinstance(series, pd.Series):
        return pd.to_numeric(series, errors="coerce")
    return pd.Series(series, index=index, dtype="float64")


def _score(series: pd.Series, *, neutral: float = 50.0, inverse: bool = False, positive_only: bool = False) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    if positive_only:
        values = values.clip(lower=0)
    if inverse:
        values = -values
    valid = values.dropna()
    if valid.empty:
        return pd.Series(neutral, index=series.index, dtype="float64")
    if valid.nunique(dropna=True) <= 1:
        if positive_only and float(valid.iloc[0]) > 0:
            return pd.Series(70.0, index=series.index, dtype="float64")
        return pd.Series(neutral, index=series.index, dtype="float64")
    return (values.rank(pct=True, method="average") * 100).fillna(neutral).astype("float64")


def _avg(columns: list[pd.Series], index: pd.Index, neutral: float = 50.0) -> pd.Series:
    clean = [pd.to_numeric(col, errors="coerce") for col in columns]
    if not clean:
        return pd.Series(neutral, index=index, dtype="float64")
    return pd.concat(clean, axis=1).mean(axis=1).fillna(neutral).astype("float64")


def _date_col(df: pd.DataFrame) -> str:
    if "trade_date" in df.columns:
        return "trade_date"
    return "date"


def _stock_col(df: pd.DataFrame) -> str:
    if "stock_code" in df.columns:
        return "stock_code"
    return "stock_id"


def _normalize_price(price: pd.DataFrame) -> pd.DataFrame:
    if price.empty:
        return pd.DataFrame(columns=["trade_date", "stock_id"])
    df = price.copy()
    df["trade_date"] = pd.to_datetime(df[_date_col(df)], errors="coerce")
    df["stock_id"] = df[_stock_col(df)].astype(str).str.strip()
    if "stock_name" not in df.columns and "name" in df.columns:
        df["stock_name"] = df["name"]
    for source, target in [
        ("Trading_Volume", "volume"),
        ("Trading_money", "trade_value"),
        ("trade_volume", "volume"),
        ("trade_value_twd", "trade_value"),
    ]:
        if source in df.columns and target not in df.columns:
            df[target] = df[source]
    for col in ["close", "volume", "trade_value"]:
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["trade_date", "stock_id"]).sort_values(["stock_id", "trade_date"])


def _latest_price_features(price: pd.DataFrame, index_price: pd.DataFrame | None, sector_alpha: pd.DataFrame | None) -> pd.DataFrame:
    p = _normalize_price(price)
    if p.empty:
        return pd.DataFrame()
    g = p.groupby("stock_id", group_keys=False)
    p["return_5d_raw"] = g["close"].pct_change(5)
    p["return_20d_raw"] = g["close"].pct_change(20)
    p["return_60d_raw"] = g["close"].pct_change(60)
    p["ma5_raw"] = g["close"].rolling(5, min_periods=1).mean().reset_index(level=0, drop=True)
    p["ma20_raw"] = g["close"].rolling(20, min_periods=1).mean().reset_index(level=0, drop=True)
    p["ma60_raw"] = g["close"].rolling(60, min_periods=1).mean().reset_index(level=0, drop=True)
    p["volatility_20d_raw"] = g["close"].pct_change().rolling(20, min_periods=2).std().reset_index(level=0, drop=True)
    rolling_max = g["close"].rolling(60, min_periods=1).max().reset_index(level=0, drop=True)
    p["max_drawdown_60d_raw"] = p["close"] / rolling_max - 1
    p["trade_value_1d_raw"] = p["trade_value"]
    p["trade_value_ma20_raw"] = g["trade_value"].rolling(20, min_periods=1).mean().reset_index(level=0, drop=True)
    p["trade_value_ratio_20d_raw"] = p["trade_value"] / p["trade_value_ma20_raw"].where(p["trade_value_ma20_raw"] > 0)
    p["turnover_proxy_raw"] = p["volume"]
    p["volume_price_sync_raw"] = (p["return_5d_raw"].fillna(0) > 0).astype(int) * p["trade_value_ratio_20d_raw"]
    p["trade_value_abnormal_raw"] = (p["trade_value_ratio_20d_raw"] - 1).clip(lower=0)
    latest = p.groupby("stock_id", as_index=False).tail(1).copy()
    latest["close_above_ma20_raw"] = (latest["close"] > latest["ma20_raw"]).map(bool).astype(object)
    latest["close_above_ma60_raw"] = (latest["close"] > latest["ma60_raw"]).map(bool).astype(object)
    latest["relative_strength_vs_taiex_raw"] = latest["return_20d_raw"]
    latest["relative_strength_vs_sector_raw"] = latest["return_20d_raw"]
    if sector_alpha is not None and not sector_alpha.empty:
        sec = sector_alpha.copy()
        if "stock_id" in latest.columns and "sector" in latest.columns and "sector" in sec.columns:
            pass
    return latest


def _institutional_features(institutional: pd.DataFrame | None) -> pd.DataFrame:
    if institutional is None or institutional.empty:
        return pd.DataFrame(columns=["stock_id"])
    df = institutional.copy()
    df["trade_date"] = pd.to_datetime(df[_date_col(df)], errors="coerce")
    df["stock_id"] = df[_stock_col(df)].astype(str).str.strip()
    investor = df.get("name", df.get("investor", "")).astype(str)
    buy = _num(df.get("buy", df.get("buy_shares", 0)), df.index)
    sell = _num(df.get("sell", df.get("sell_shares", 0)), df.index)
    net = _num(df.get("net", buy - sell), df.index)
    df["net"] = net
    df["bucket"] = "dealer"
    df.loc[investor.str.contains("Foreign|外資", case=False, regex=True), "bucket"] = "foreign"
    df.loc[investor.str.contains("Investment|Trust|投信", case=False, regex=True), "bucket"] = "investment_trust"
    pivot = (
        df.groupby(["stock_id", "trade_date", "bucket"], dropna=False)["net"]
        .sum()
        .unstack("bucket")
        .reset_index()
        .fillna(0)
        .sort_values(["stock_id", "trade_date"])
    )
    for bucket, prefix in [("foreign", "foreign"), ("investment_trust", "investment_trust"), ("dealer", "dealer")]:
        if bucket not in pivot.columns:
            pivot[bucket] = 0.0
        g = pivot.groupby("stock_id")[bucket]
        pivot[f"{prefix}_buy_1d_raw"] = pivot[bucket]
        pivot[f"{prefix}_buy_5d_raw"] = g.rolling(5, min_periods=1).sum().reset_index(level=0, drop=True)
        pivot[f"{prefix}_buy_20d_raw"] = g.rolling(20, min_periods=1).sum().reset_index(level=0, drop=True)
    pivot["institution_sync_score_raw"] = (
        (pivot["foreign"] > 0).astype(int)
        + (pivot["investment_trust"] > 0).astype(int)
        + (pivot["dealer"] > 0).astype(int)
    ) / 3
    pivot["institution_accumulation_score_raw"] = (
        pivot["foreign_buy_20d_raw"] + pivot["investment_trust_buy_20d_raw"] + pivot["dealer_buy_20d_raw"]
    )
    pivot["institutional_sync_raw"] = pivot["institution_sync_score_raw"]
    inflow = (pivot["foreign"] + pivot["investment_trust"] + pivot["dealer"]) > 0
    pivot["consecutive_inflow_days_raw"] = inflow.groupby(pivot["stock_id"]).transform(
        lambda s: s.astype(int).groupby((~s).cumsum()).cumsum()
    )
    return pivot.groupby("stock_id", as_index=False).tail(1)


def _margin_features(margin: pd.DataFrame | None) -> pd.DataFrame:
    if margin is None or margin.empty:
        return pd.DataFrame(columns=["stock_id"])
    df = margin.copy()
    df["trade_date"] = pd.to_datetime(df[_date_col(df)], errors="coerce")
    df["stock_id"] = df[_stock_col(df)].astype(str).str.strip()
    margin_col = next((c for c in ["MarginPurchaseTodayBalance", "margin_balance", "margin_purchase_balance"] if c in df.columns), None)
    short_col = next((c for c in ["ShortSaleTodayBalance", "short_balance", "short_sale_balance"] if c in df.columns), None)
    df["margin_balance_raw"] = _num(df[margin_col], df.index) if margin_col else pd.NA
    df["short_balance_raw"] = _num(df[short_col], df.index) if short_col else pd.NA
    df = df.sort_values(["stock_id", "trade_date"])
    g = df.groupby("stock_id")
    df["margin_balance_change_1d_raw"] = g["margin_balance_raw"].diff()
    df["margin_balance_change_5d_raw"] = g["margin_balance_raw"].diff(5)
    df["margin_balance_change_20d_raw"] = g["margin_balance_raw"].diff(20)
    df["short_balance_change_1d_raw"] = g["short_balance_raw"].diff()
    df["short_balance_change_5d_raw"] = g["short_balance_raw"].diff(5)
    df["margin_overheat_score_raw"] = df["margin_balance_change_5d_raw"]
    df["short_covering_score_raw"] = -df["short_balance_change_5d_raw"]
    df["credit_health_score_raw"] = -df["margin_balance_change_5d_raw"].fillna(0) + df["short_covering_score_raw"].fillna(0)
    return df.groupby("stock_id", as_index=False).tail(1)


def _revenue_features(revenue: pd.DataFrame | None) -> pd.DataFrame:
    if revenue is None or revenue.empty:
        return pd.DataFrame(columns=["stock_id"])
    df = revenue.copy()
    df["trade_date"] = pd.to_datetime(df[_date_col(df)], errors="coerce")
    df["stock_id"] = df[_stock_col(df)].astype(str).str.strip()
    df["revenue"] = _num(df.get("revenue", df.get("monthly_revenue", pd.NA)), df.index)
    df = df.dropna(subset=["trade_date", "stock_id", "revenue"]).sort_values(["stock_id", "trade_date"])
    df["month"] = df["trade_date"].dt.month
    df["year"] = df["trade_date"].dt.year
    df["revenue_mom_raw"] = df.groupby("stock_id")["revenue"].pct_change()
    df["revenue_6m_trend_raw"] = df.groupby("stock_id")["revenue"].pct_change(6)
    yoy = df[["stock_id", "month", "year", "revenue"]].rename(columns={"revenue": "prev_year_revenue"})
    df["prev_year"] = df["year"] - 1
    df = df.merge(yoy, left_on=["stock_id", "month", "prev_year"], right_on=["stock_id", "month", "year"], how="left", suffixes=("", "_yoy"))
    df["revenue_yoy_raw"] = (df["revenue"] - df["prev_year_revenue"]) / df["prev_year_revenue"].where(df["prev_year_revenue"] > 0)
    df["revenue_3m_yoy_raw"] = df.groupby("stock_id")["revenue_yoy_raw"].rolling(3, min_periods=1).mean().reset_index(level=0, drop=True)
    df["revenue_acceleration_score_raw"] = df["revenue_yoy_raw"].fillna(0) + df["revenue_mom_raw"].fillna(0)
    return df.groupby("stock_id", as_index=False).tail(1)


def _financial_features(financials: pd.DataFrame | None, per: pd.DataFrame | None) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if financials is not None and not financials.empty:
        df = financials.copy()
        df["stock_id"] = df[_stock_col(df)].astype(str).str.strip()
        if _date_col(df) in df.columns:
            df["trade_date"] = pd.to_datetime(df[_date_col(df)], errors="coerce")
        for col in [
            "eps_ttm",
            "gross_margin",
            "operating_margin",
            "net_margin",
            "roe",
            "debt_ratio",
            "operating_cash_flow",
            "free_cash_flow_proxy",
        ]:
            if col not in df.columns:
                df[col] = pd.NA
            df[f"{col}_raw"] = _num(df[col], df.index)
        frames.append(df.groupby("stock_id", as_index=False).tail(1))
    if per is not None and not per.empty:
        pv = per.copy()
        pv["stock_id"] = pv[_stock_col(pv)].astype(str).str.strip()
        for source, target in [("PER", "pe_ratio"), ("PBR", "pb_ratio"), ("dividend_yield", "dividend_yield")]:
            if source in pv.columns and target not in pv.columns:
                pv[target] = pv[source]
        for col in ["pe_ratio", "pb_ratio", "dividend_yield"]:
            if col not in pv.columns:
                pv[col] = pd.NA
            pv[f"{col}_raw"] = _num(pv[col], pv.index)
        frames.append(pv.groupby("stock_id", as_index=False).tail(1))
    if not frames:
        return pd.DataFrame(columns=["stock_id"])
    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on="stock_id", how="outer", suffixes=("", "_extra"))
    return out


def compute_finmind_factors(
    *,
    price: pd.DataFrame,
    institutional: pd.DataFrame | None = None,
    margin: pd.DataFrame | None = None,
    revenue: pd.DataFrame | None = None,
    financials: pd.DataFrame | None = None,
    per: pd.DataFrame | None = None,
    sector_alpha: pd.DataFrame | None = None,
    index_price: pd.DataFrame | None = None,
) -> pd.DataFrame:
    base = _latest_price_features(price, index_price, sector_alpha)
    if base.empty:
        return pd.DataFrame()

    for extra in [
        _institutional_features(institutional),
        _margin_features(margin),
        _revenue_features(revenue),
        _financial_features(financials, per),
    ]:
        if not extra.empty:
            merge_extra = extra.drop(columns=[c for c in ["trade_date"] if c in extra.columns]).copy()
            duplicate_cols = [col for col in merge_extra.columns if col != "stock_id" and col in base.columns]
            if duplicate_cols:
                merge_extra = merge_extra.drop(columns=duplicate_cols)
            base = base.merge(merge_extra, on="stock_id", how="left")

    base["sector_alpha_raw"] = _num(base.get("sector_alpha_score", 50), base.index).fillna(50)
    base["sector_strength_raw"] = base["sector_alpha_raw"]

    raw_defaults = {
        "relative_strength_vs_taiex_raw": 0.0,
        "relative_strength_vs_sector_raw": 0.0,
        "margin_balance_change_1d_raw": 0.0,
        "margin_balance_change_5d_raw": 0.0,
        "margin_balance_change_20d_raw": 0.0,
        "short_balance_change_1d_raw": 0.0,
        "short_balance_change_5d_raw": 0.0,
        "margin_overheat_score_raw": 0.0,
        "short_covering_score_raw": 0.0,
        "credit_health_score_raw": 0.0,
        "eps_ttm_raw": pd.NA,
        "gross_margin_raw": pd.NA,
        "operating_margin_raw": pd.NA,
        "net_margin_raw": pd.NA,
        "roe_raw": pd.NA,
        "debt_ratio_raw": pd.NA,
        "operating_cash_flow_raw": pd.NA,
        "free_cash_flow_proxy_raw": pd.NA,
        "pe_ratio_raw": pd.NA,
        "pb_ratio_raw": pd.NA,
        "dividend_yield_raw": pd.NA,
        "institution_sync_score_raw": 0.0,
        "institution_accumulation_score_raw": 0.0,
        "institutional_sync_raw": 0.0,
        "consecutive_inflow_days_raw": 0.0,
        "revenue_yoy_raw": pd.NA,
        "revenue_mom_raw": pd.NA,
        "revenue_3m_yoy_raw": pd.NA,
        "revenue_6m_trend_raw": pd.NA,
        "revenue_acceleration_score_raw": pd.NA,
    }
    for col, value in raw_defaults.items():
        if col not in base.columns:
            base[col] = value

    base["liquidity_score_raw"] = base["trade_value_ma20_raw"]
    base["quality_score_raw"] = _avg(
        [
            _score(_num(base["gross_margin_raw"], base.index)),
            _score(_num(base["operating_margin_raw"], base.index)),
            _score(_num(base["roe_raw"], base.index)),
            _score(_num(base["debt_ratio_raw"], base.index), inverse=True),
            _score(_num(base["operating_cash_flow_raw"], base.index)),
        ],
        base.index,
    )
    base["valuation_score_raw"] = _avg(
        [
            _score(_num(base["pe_ratio_raw"], base.index), inverse=True),
            _score(_num(base["pb_ratio_raw"], base.index), inverse=True),
            _score(_num(base["dividend_yield_raw"], base.index), positive_only=True),
        ],
        base.index,
    )
    base["not_overheated_score_raw"] = 100 - _score(_num(base["return_20d_raw"], base.index), positive_only=True)
    base["main_force_proxy_raw"] = _avg(
        [
            _score(_num(base.get("volume_price_sync_raw", 0), base.index), positive_only=True),
            _score(_num(base["institutional_sync_raw"], base.index), positive_only=True),
            _score(_num(base.get("trade_value_abnormal_raw", 0), base.index), positive_only=True),
            _score(_num(base["consecutive_inflow_days_raw"], base.index), positive_only=True),
            _score(_num(base["sector_strength_raw"], base.index), positive_only=True),
            _num(base["not_overheated_score_raw"], base.index),
        ],
        base.index,
    )
    base["overheat_penalty_raw"] = _score(_num(base["return_20d_raw"], base.index), positive_only=True).where(
        _num(base["return_20d_raw"], base.index).fillna(0) > 0.15,
        0,
    )
    base["high_volatility_penalty_raw"] = _score(_num(base["volatility_20d_raw"], base.index), positive_only=True).where(
        _num(base["volatility_20d_raw"], base.index).fillna(0) > 0.04,
        0,
    )
    base["low_liquidity_penalty_raw"] = (100 - _score(_num(base["trade_value_ma20_raw"], base.index), positive_only=True)).where(
        _num(base["trade_value_ma20_raw"], base.index).fillna(0) < 50_000_000,
        0,
    )
    base["weak_financial_penalty_raw"] = (100 - base["quality_score_raw"]).where(base["quality_score_raw"] < 35, 0)
    base["margin_overheat_penalty_raw"] = _score(_num(base["margin_balance_change_5d_raw"], base.index), positive_only=True).where(
        _num(base["margin_balance_change_5d_raw"], base.index).fillna(0) > 0,
        0,
    )
    base["risk_penalty_total_raw"] = (
        _num(base["overheat_penalty_raw"], base.index).fillna(0) * 0.12
        + _num(base["high_volatility_penalty_raw"], base.index).fillna(0) * 0.10
        + _num(base["low_liquidity_penalty_raw"], base.index).fillna(0) * 0.12
        + _num(base["weak_financial_penalty_raw"], base.index).fillna(0) * 0.08
        + _num(base["margin_overheat_penalty_raw"], base.index).fillna(0) * 0.05
    )

    direct_scores = {
        "close_above_ma20": base["close_above_ma20_raw"].map(lambda v: 100.0 if bool(v) else 0.0),
        "close_above_ma60": base["close_above_ma60_raw"].map(lambda v: 100.0 if bool(v) else 0.0),
        "sector_alpha": _num(base["sector_alpha_raw"], base.index).clip(0, 100),
        "sector_strength": _num(base["sector_strength_raw"], base.index).clip(0, 100),
        "institution_sync_score": _num(base["institution_sync_score_raw"], base.index).clip(0, 1) * 100,
        "institutional_sync": _num(base["institutional_sync_raw"], base.index).clip(0, 1) * 100,
        "quality_score": _num(base["quality_score_raw"], base.index).clip(0, 100),
        "valuation_score": _num(base["valuation_score_raw"], base.index).clip(0, 100),
        "not_overheated_score": _num(base["not_overheated_score_raw"], base.index).clip(0, 100),
        "main_force_proxy": _num(base["main_force_proxy_raw"], base.index).clip(0, 100),
        "risk_penalty_total": _num(base["risk_penalty_total_raw"], base.index).clip(0, 100),
        "overheat_penalty": _num(base["overheat_penalty_raw"], base.index).clip(0, 100),
        "high_volatility_penalty": _num(base["high_volatility_penalty_raw"], base.index).clip(0, 100),
        "low_liquidity_penalty": _num(base["low_liquidity_penalty_raw"], base.index).clip(0, 100),
        "weak_financial_penalty": _num(base["weak_financial_penalty_raw"], base.index).clip(0, 100),
        "margin_overheat_penalty": _num(base["margin_overheat_penalty_raw"], base.index).clip(0, 100),
    }
    for factor in FACTOR_COLUMNS:
        raw_col = f"{factor}_raw"
        if factor in direct_scores:
            base[factor] = direct_scores[factor]
        elif raw_col in base.columns:
            inverse = factor in {"volatility_20d", "max_drawdown_60d", "margin_overheat_score", "pe_ratio", "pb_ratio", "debt_ratio"}
            base[factor] = _score(_num(base[raw_col], base.index), inverse=inverse, positive_only=False)
        else:
            base[factor] = 50.0
            base[raw_col] = pd.NA
    return base.reset_index(drop=True)


def write_factors_outputs(factors: pd.DataFrame, *, processed_path: Path, public_json_path: Path) -> None:
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    public_json_path.parent.mkdir(parents=True, exist_ok=True)
    factors.to_parquet(processed_path, index=False)
    latest = factors.copy()
    if "trade_date" in latest.columns:
        latest["trade_date"] = pd.to_datetime(latest["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    payload = {
        "generated_at": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "records": latest.replace({pd.NA: None}).to_dict(orient="records"),
        "note": "FinMind factors are observation-only supplemental analytics, not buy or sell advice.",
    }
    public_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
