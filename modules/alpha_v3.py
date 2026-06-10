from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


ALPHA_V3_WEIGHTS = {
    "sector_alpha": 0.15,
    "foreign_score": 0.15,
    "trust_score": 0.15,
    "trade_value_score": 0.10,
    "momentum_score": 0.10,
    "revenue_score": 0.10,
    "quality_score": 0.08,
    "valuation_score": 0.07,
    "credit_health_score": 0.05,
    "main_force_proxy": 0.05,
}


def _series(df: pd.DataFrame, col: str, default: float = 50.0) -> pd.Series:
    if col not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce").fillna(default).astype("float64")


def _avg(df: pd.DataFrame, cols: list[str], default: float = 50.0) -> pd.Series:
    present = [_series(df, col, default) for col in cols if col in df.columns]
    if not present:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.concat(present, axis=1).mean(axis=1).fillna(default)


def _reason_codes(row: pd.Series) -> list[str]:
    codes: list[str] = []
    if float(row.get("sector_alpha") or 0) >= 70:
        codes.append("產業強勢")
    if float(row.get("foreign_score") or 0) >= 70 and float(row.get("trust_score") or 0) >= 70:
        codes.append("法人同步")
    if float(row.get("revenue_score") or 0) >= 70:
        codes.append("營收加速")
    if float(row.get("quality_score") or 0) >= 70:
        codes.append("財務品質")
    if float(row.get("main_force_proxy") or 0) >= 70:
        codes.append("主力估算")
    if not codes:
        codes.append("中性觀察")
    return codes


def _risk_tags(row: pd.Series) -> list[str]:
    tags: list[str] = []
    if float(row.get("overheat_penalty") or 0) > 0:
        tags.append("過熱")
    if float(row.get("high_volatility_penalty") or 0) > 0:
        tags.append("高波動")
    if float(row.get("low_liquidity_penalty") or 0) > 0:
        tags.append("流動性不足")
    if float(row.get("weak_financial_penalty") or 0) > 0:
        tags.append("財務轉弱")
    if float(row.get("margin_overheat_penalty") or 0) > 0:
        tags.append("融資偏熱")
    return tags


def _confidence(df: pd.DataFrame, components: pd.DataFrame) -> pd.Series:
    component_cols = list(ALPHA_V3_WEIGHTS.keys())
    source_cols = [
        "sector_alpha",
        "foreign_buy_5d",
        "foreign_buy_20d",
        "investment_trust_buy_5d",
        "investment_trust_buy_20d",
        "trade_value_ratio_20d",
        "return_20d",
        "return_60d",
        "revenue_acceleration_score",
        "quality_score",
        "valuation_score",
        "credit_health_score",
        "main_force_proxy",
    ]
    availability = pd.DataFrame(
        {col: df[col].notna() if col in df.columns else pd.Series(False, index=df.index) for col in source_cols}
    ).mean(axis=1) * 100
    factor_consistency = components[component_cols].std(axis=1).map(lambda v: max(0.0, 100.0 - float(v)))
    institutional_sync = _series(df, "institution_sync_score", 50.0)
    liquidity = _series(df, "liquidity_score", 50.0)
    backtest_win_rate = _series(df, "backtest_win_rate", 0.5).clip(0, 1) * 100
    return (
        availability * 0.30
        + backtest_win_rate * 0.20
        + factor_consistency * 0.20
        + institutional_sync * 0.15
        + liquidity * 0.15
    ).clip(0, 100)


def compute_alpha_v3(factors: pd.DataFrame) -> pd.DataFrame:
    if factors.empty:
        return pd.DataFrame()
    df = factors.copy()
    if "stock_id" not in df.columns and "stock_code" in df.columns:
        df["stock_id"] = df["stock_code"].astype(str)
    components = pd.DataFrame(index=df.index)
    components["sector_alpha"] = _series(df, "sector_alpha", 50.0)
    components["foreign_score"] = _avg(df, ["foreign_buy_5d", "foreign_buy_20d"], 50.0)
    components["trust_score"] = _avg(df, ["investment_trust_buy_5d", "investment_trust_buy_20d"], 50.0)
    components["trade_value_score"] = _series(df, "trade_value_ratio_20d", 50.0)
    components["momentum_score"] = _avg(df, ["return_20d", "return_60d"], 50.0)
    components["revenue_score"] = _series(df, "revenue_acceleration_score", 50.0)
    components["quality_score"] = _series(df, "quality_score", 50.0)
    components["valuation_score"] = _series(df, "valuation_score", 50.0)
    components["credit_health_score"] = _series(df, "credit_health_score", 50.0)
    components["main_force_proxy"] = _series(df, "main_force_proxy", 50.0)
    risk = _series(df, "risk_penalty_total", 0.0)
    score = sum(components[col] * weight for col, weight in ALPHA_V3_WEIGHTS.items()) - risk
    out = df.copy()
    for col in components.columns:
        out[col] = components[col].clip(0, 100)
    out["risk_penalty_total"] = risk.clip(0, 100)
    out["stock_alpha_v3"] = score.clip(0, 100)
    out["alpha_breakdown"] = components.round(4).to_dict(orient="records")
    out["alpha_reason_codes"] = out.apply(_reason_codes, axis=1)
    out["risk_tags"] = out.apply(_risk_tags, axis=1)
    out["confidence_score"] = _confidence(df, components).round(4)
    return out.reset_index(drop=True)


def write_alpha_v3_outputs(alpha: pd.DataFrame, *, processed_path: Path, public_json_path: Path) -> None:
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    public_json_path.parent.mkdir(parents=True, exist_ok=True)
    alpha.to_parquet(processed_path, index=False)
    payload = {
        "generated_at": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "records": alpha.replace({pd.NA: None}).to_dict(orient="records"),
        "disclaimer": "All recommendations are observation candidates only. No buy or sell advice is generated.",
    }
    public_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
