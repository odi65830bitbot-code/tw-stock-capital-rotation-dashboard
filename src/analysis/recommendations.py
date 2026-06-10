from __future__ import annotations

import re
from typing import Iterable

import pandas as pd


MIN_TRADE_VALUE_TWD = 50_000_000
MIN_TRADE_VOLUME = 200_000
ABNORMAL_CHANGE_PCT = 9.5

STATUS_OBSERVE = "觀察"
STATUS_SCALE_OBSERVE = "分批觀察"
STATUS_OVERHEATED = "過熱"
STATUS_AVOID = "避開"


_SUPPLEMENTAL_PRODUCT_KEYWORDS = (
    "ETF",
    "ETN",
    "元大",
    "國泰",
    "富邦",
    "群益",
    "凱基",
    "永豐",
    "兆豐",
    "中信",
    "美債",
    "反1",
    "正2",
    "期",
    "債",
    "購",
    "售",
    "牛",
    "熊",
)


def _latest_only(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "trade_date" not in df.columns:
        return df.copy()
    out = df.copy()
    out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce")
    latest = out["trade_date"].max()
    return out[out["trade_date"] == latest].copy()


def _numeric(df: pd.DataFrame, col: str, default: float | None = None) -> pd.Series:
    if col not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce")


def _percentile_score(series: pd.Series, *, positive_only: bool = False, neutral: float = 50.0) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    if positive_only:
        values = values.clip(lower=0)
    valid = values.dropna()
    if valid.empty:
        return pd.Series(neutral, index=series.index, dtype="float64")
    if valid.nunique(dropna=True) <= 1:
        score = pd.Series(neutral, index=series.index, dtype="float64")
        if positive_only:
            score = score.where(values.fillna(0) <= 0, 70.0)
        return score
    return (values.rank(pct=True, method="average") * 100).fillna(neutral).astype("float64")


def _average_components(components: list[pd.Series], index: pd.Index, neutral: float = 50.0) -> pd.Series:
    clean = [pd.to_numeric(component, errors="coerce") for component in components]
    if not clean:
        return pd.Series(neutral, index=index, dtype="float64")
    return pd.concat(clean, axis=1).mean(axis=1).fillna(neutral).astype("float64")


def _sector_merge_key(value: object) -> str:
    text = str(value or "").strip()
    aliases = {
        "水泥工業": "水泥",
        "食品工業": "食品",
        "塑膠工業": "塑膠",
        "化學工業": "化工",
        "電腦及週邊設備業": "電腦及週邊設備",
        "電子零組件業": "電子零組件",
        "半導體業": "半導體",
    }
    if text in aliases:
        return aliases[text]
    for suffix in ("產業", "工業", "業"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text


def _is_common_stock(code: object, name: object) -> bool:
    text_code = str(code or "").strip().upper()
    text_name = str(name or "").strip().upper()
    if not re.fullmatch(r"\d{4}", text_code):
        return False
    return not any(keyword.upper() in text_name for keyword in _SUPPLEMENTAL_PRODUCT_KEYWORDS)


def _change_pct(df: pd.DataFrame) -> pd.Series:
    close = _numeric(df, "close")
    change = _numeric(df, "change")
    prev_close = close - change
    pct = change / prev_close.where(prev_close > 0) * 100.0
    return pct.replace([float("inf"), -float("inf")], pd.NA).astype("float64")


def _risk_labels(row: pd.Series) -> list[str]:
    labels: list[str] = []
    if not bool(row.get("is_common_stock", False)):
        labels.append("非普通股")
    if bool(row.get("low_liquidity", False)):
        labels.append("流動性不足")
    if bool(row.get("abnormal_volatility", False)):
        labels.append("異常波動")
    if not bool(row.get("has_institutional_flow", False)):
        labels.append("法人資料不足")
    if str(row.get("industry", "UNKNOWN")) == "UNKNOWN":
        labels.append("產業分類不足")
    return labels


def _build_sector_context(sector_alpha: pd.DataFrame, sector_flow: pd.DataFrame) -> pd.DataFrame:
    alpha = _latest_only(sector_alpha)
    flow = _latest_only(sector_flow)
    if alpha.empty and flow.empty:
        return pd.DataFrame()

    if alpha.empty:
        base = flow.copy()
        base["sector_alpha_score"] = pd.NA
    elif flow.empty:
        base = alpha.copy()
        base["three_party_net_shares"] = pd.NA
    else:
        base = alpha.merge(
            flow,
            on=["trade_date", "market", "industry"],
            how="outer",
            suffixes=("", "_flow"),
        )

    base["sector_alpha_score"] = _numeric(base, "sector_alpha_score")
    base["sector_strength_component"] = _percentile_score(base["sector_alpha_score"], positive_only=True)
    base["sector_flow_component"] = _percentile_score(_numeric(base, "three_party_net_shares"), positive_only=True)
    base["moneydj_accel_component"] = _percentile_score(
        _numeric(base, "moneydj_flow_rate_accel_pct"),
        positive_only=False,
        neutral=50.0,
    )
    base["sector_candidate_score"] = (
        base["sector_strength_component"] * 0.55
        + base["sector_flow_component"] * 0.30
        + base["moneydj_accel_component"] * 0.15
    )
    return base


def build_stock_alpha_breakdown(
    stock_alpha: pd.DataFrame,
    sector_alpha: pd.DataFrame,
    sector_flow: pd.DataFrame | None = None,
    moneydj_sector_indicators: pd.DataFrame | None = None,
    finmind_composite_indicators: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if stock_alpha.empty:
        return pd.DataFrame()

    df = _latest_only(stock_alpha)
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["stock_code"] = df["stock_code"].astype(str)
    df["industry"] = df.get("industry", pd.Series("UNKNOWN", index=df.index)).fillna("UNKNOWN")
    df["trade_volume"] = _numeric(df, "trade_volume")
    df["trade_value_twd"] = _numeric(df, "trade_value_twd")
    df["close"] = _numeric(df, "close")
    df["change"] = _numeric(df, "change", 0.0)
    df["foreign_net_shares"] = _numeric(df, "foreign_net_shares")
    df["dealer_net_shares"] = _numeric(df, "dealer_net_shares")
    df["trustee_net_shares"] = _numeric(df, "trustee_net_shares")
    df["three_party_net_shares"] = _numeric(df, "three_party_net_shares")
    df["flow_rate"] = _numeric(df, "flow_rate")
    missing_flow_rate = df["flow_rate"].isna()
    df.loc[missing_flow_rate, "flow_rate"] = (
        df.loc[missing_flow_rate, "three_party_net_shares"].abs()
        / df.loc[missing_flow_rate, "trade_volume"].where(df.loc[missing_flow_rate, "trade_volume"] > 0)
    )
    df["has_institutional_flow"] = df.get("has_institutional_flow", df["three_party_net_shares"].notna()).fillna(False)

    sector_flow_df = sector_flow if sector_flow is not None else pd.DataFrame()
    sector_context = _build_sector_context(sector_alpha, sector_flow_df)
    if not sector_context.empty:
        context_cols = [
            "trade_date",
            "market",
            "industry",
            "sector_alpha_score",
            "sector_strength_component",
            "sector_candidate_score",
            "moneydj_flow_rate_accel_pct",
            "moneydj_relative_strength_20d_pct",
        ]
        existing_context_cols = [c for c in context_cols if c in sector_context.columns]
        df = df.merge(
            sector_context[existing_context_cols].drop_duplicates(["trade_date", "market", "industry"]),
            on=["trade_date", "market", "industry"],
            how="left",
        )
    else:
        df["sector_alpha_score"] = pd.NA
        df["sector_strength_component"] = 50.0
        df["sector_candidate_score"] = 50.0

    if moneydj_sector_indicators is not None and not moneydj_sector_indicators.empty:
        supplement = _latest_only(moneydj_sector_indicators)
        supplement = supplement.copy()
        supplement["_industry_key"] = supplement["industry"].map(_sector_merge_key)
        df["_industry_key"] = df["industry"].map(_sector_merge_key)
        extra_cols = [
            "trade_date",
            "market",
            "_industry_key",
            "moneydj_flow_rate_5d_avg_pct",
            "moneydj_flow_rate_20d_avg_pct",
            "moneydj_validation_status",
        ]
        df = df.merge(
            supplement[[c for c in extra_cols if c in supplement.columns]].drop_duplicates(
                ["trade_date", "market", "_industry_key"]
            ),
            on=["trade_date", "market", "_industry_key"],
            how="left",
        ).drop(columns=["_industry_key"])

    if finmind_composite_indicators is not None and not finmind_composite_indicators.empty:
        finmind = finmind_composite_indicators.copy()
        finmind["stock_code"] = finmind["stock_code"].astype(str).str.strip()
        finmind = finmind.drop_duplicates(["stock_code"], keep="last")
        df = df.merge(finmind, on="stock_code", how="left")

    df["change_pct"] = _change_pct(df)
    df["is_common_stock"] = [
        _is_common_stock(code, name) for code, name in zip(df["stock_code"], df.get("stock_name", ""))
    ]
    df["low_liquidity"] = (df["trade_value_twd"].fillna(0) < MIN_TRADE_VALUE_TWD) | (
        df["trade_volume"].fillna(0) < MIN_TRADE_VOLUME
    )
    df["abnormal_volatility"] = df["change_pct"].abs().fillna(0) >= ABNORMAL_CHANGE_PCT
    df["disposition_data_available"] = False
    df["full_delivery_data_available"] = False
    df["is_disposition"] = False
    df["is_full_delivery"] = False

    df["sector_alpha_component"] = df["sector_strength_component"].fillna(50.0).astype("float64")
    df["main_buy_component"] = _percentile_score(df["flow_rate"].abs(), positive_only=True)
    df["foreign_component"] = _percentile_score(df["foreign_net_shares"], positive_only=True)
    df["trust_component"] = _percentile_score(df["trustee_net_shares"], positive_only=True)
    df["trade_value_component"] = _percentile_score(df["trade_value_twd"], positive_only=True)
    df["momentum_component"] = _percentile_score(df["change_pct"], positive_only=False)
    revenue_components: list[pd.Series] = []
    if "finmind_revenue_yoy_pct" in df.columns:
        revenue_components.append(_percentile_score(_numeric(df, "finmind_revenue_yoy_pct"), neutral=50.0))
    if "finmind_revenue_mom_pct" in df.columns:
        revenue_components.append(_percentile_score(_numeric(df, "finmind_revenue_mom_pct"), neutral=50.0))
    df["revenue_component"] = _average_components(revenue_components, df.index)
    df["revenue_data_available"] = bool(revenue_components)

    quality_components: list[pd.Series] = []
    if "finmind_per" in df.columns:
        per = _numeric(df, "finmind_per")
        quality_components.append(_percentile_score((1 / per.where(per > 0)) * 1000, neutral=50.0))
    if "finmind_pbr" in df.columns:
        pbr = _numeric(df, "finmind_pbr")
        quality_components.append(_percentile_score((1 / pbr.where(pbr > 0)) * 1000, neutral=50.0))
    if "finmind_dividend_yield_pct" in df.columns:
        quality_components.append(_percentile_score(_numeric(df, "finmind_dividend_yield_pct"), positive_only=True, neutral=50.0))
    df["quality_component"] = _average_components(quality_components, df.index)
    df["financial_quality_data_available"] = bool(quality_components)
    df["trade_value_expansion_proxy"] = True

    df["risk_penalty"] = 0.0
    df.loc[~df["is_common_stock"], "risk_penalty"] += 100.0
    df.loc[df["low_liquidity"], "risk_penalty"] += 35.0
    df.loc[df["abnormal_volatility"], "risk_penalty"] += 30.0
    df.loc[~df["has_institutional_flow"].astype(bool), "risk_penalty"] += 10.0
    df.loc[df["industry"].astype(str).eq("UNKNOWN"), "risk_penalty"] += 5.0

    df["alpha_score_total"] = (
        df["sector_alpha_component"] * 0.20
        + df["main_buy_component"] * 0.20
        + df["foreign_component"] * 0.15
        + df["trust_component"] * 0.15
        + df["trade_value_component"] * 0.10
        + df["momentum_component"] * 0.10
        + df["revenue_component"] * 0.05
        + df["quality_component"] * 0.05
        - df["risk_penalty"]
    ).clip(lower=0.0, upper=100.0)

    df["risk_flags"] = df.apply(lambda row: "、".join(_risk_labels(row)), axis=1)
    df["is_excluded"] = (
        (~df["is_common_stock"])
        | df["low_liquidity"]
        | df["abnormal_volatility"]
        | df["is_disposition"]
        | df["is_full_delivery"]
    )
    df["exclusion_reason"] = df["risk_flags"].where(df["is_excluded"], "")
    df["suggested_status"] = df.apply(_suggest_status, axis=1)
    df["is_excluded"] = df["is_excluded"].map(bool).astype(object)
    return df.sort_values("alpha_score_total", ascending=False).reset_index(drop=True)


def _suggest_status(row: pd.Series) -> str:
    if bool(row.get("is_excluded", False)) or float(row.get("alpha_score_total") or 0.0) < 35.0:
        return STATUS_AVOID
    if float(row.get("risk_penalty") or 0.0) >= 20.0 or float(row.get("momentum_component") or 0.0) >= 92.0:
        return STATUS_OVERHEATED
    if float(row.get("alpha_score_total") or 0.0) >= 70.0:
        return STATUS_OBSERVE
    if float(row.get("alpha_score_total") or 0.0) >= 55.0:
        return STATUS_SCALE_OBSERVE
    return STATUS_OBSERVE


def _reason_text(row: pd.Series) -> tuple[str, str, str, str, str]:
    code = str(row.get("stock_code", ""))
    name = str(row.get("stock_name", ""))
    industry = str(row.get("industry", "UNKNOWN"))
    alpha = float(row.get("alpha_score_total") or 0.0)
    summary = f"{code} {name} 屬於 {industry}，今日資金訊號分數 {alpha:.1f}/100，列入觀察標的。"
    reason_1 = f"產業 Alpha 位階 {float(row.get('sector_alpha_component') or 0.0):.0f}/100，產業資金排序相對靠前。"
    reason_2 = (
        f"主力分數 {float(row.get('main_buy_component') or 0.0):.0f}/100，"
        f"三大法人淨流入 {float(row.get('three_party_net_shares') or 0.0):,.0f} 股。"
    )
    if bool(row.get("revenue_data_available", False)) or bool(row.get("financial_quality_data_available", False)):
        reason_3 = (
            f"營收分數 {float(row.get('revenue_component') or 0.0):.0f}/100，"
            f"估值品質分數 {float(row.get('quality_component') or 0.0):.0f}/100。"
        )
    else:
        reason_3 = (
            f"外資/投信分數 {float(row.get('foreign_component') or 0.0):.0f}/"
            f"{float(row.get('trust_component') or 0.0):.0f}，成交值分數 {float(row.get('trade_value_component') or 0.0):.0f}。"
        )
    risk = str(row.get("risk_flags") or "").strip()
    if not risk:
        if float(row.get("momentum_component") or 0.0) >= 90.0:
            risk = "短線動能偏熱，需留意隔日量價是否延續"
        else:
            risk = "需留意盤後消息、隔日量能與大盤方向變化"
    return summary, reason_1, reason_2, reason_3, risk


def _summary_rows(sector_context: pd.DataFrame, candidates: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not sector_context.empty:
        sector_pool = sector_context[sector_context["industry"].astype(str).ne("UNKNOWN")].copy()
        if sector_pool.empty:
            sector_pool = sector_context.copy()
        sector = sector_pool.sort_values("sector_candidate_score", ascending=False).iloc[0]
        rows.append(
            {
                "summary_type": "strongest_sector",
                "market": sector.get("market"),
                "industry": sector.get("industry"),
                "score": float(sector.get("sector_candidate_score") or 0.0),
                "description": "今日產業 Alpha 與資金流向綜合排序最高",
            }
        )

        rotation = sector_pool.copy()
        rotation["rotation_score"] = (
            _numeric(rotation, "moneydj_flow_rate_accel_pct").fillna(0) * 10
            + _numeric(rotation, "three_party_net_shares").fillna(0).rank(pct=True) * 100
            + _numeric(rotation, "sector_alpha_score").fillna(0).rank(pct=True) * 100
        )
        rotation = rotation.sort_values("rotation_score", ascending=False).iloc[0]
        rows.append(
            {
                "summary_type": "new_rotation_sector",
                "market": rotation.get("market"),
                "industry": rotation.get("industry"),
                "score": float(rotation.get("rotation_score") or 0.0),
                "description": "資金加速度與相對強度改善的輪動候選產業",
            }
        )

        fading = sector_pool.copy()
        fading["fading_score"] = _numeric(fading, "three_party_net_shares").fillna(0) + (
            _numeric(fading, "moneydj_flow_rate_accel_pct").fillna(0) * 1_000_000
        )
        fading = fading.sort_values("fading_score", ascending=True).iloc[0]
        rows.append(
            {
                "summary_type": "fading_sector",
                "market": fading.get("market"),
                "industry": fading.get("industry"),
                "score": float(fading.get("fading_score") or 0.0),
                "description": "資金訊號轉弱或流出較明顯的退潮觀察產業",
            }
        )

    if not candidates.empty:
        rows.append(
            {
                "summary_type": "candidate_count",
                "market": "ALL",
                "industry": "ALL",
                "score": int(len(candidates)),
                "description": "通過流動性、商品類型與異常波動篩選的候選標的數",
            }
        )
        market_flow = (
            candidates.groupby("market", dropna=False)["three_party_net_shares"]
            .sum(min_count=1)
            .reset_index()
            .sort_values("three_party_net_shares", ascending=False)
        )
        for _, row in market_flow.iterrows():
            rows.append(
                {
                    "summary_type": "market_direction",
                    "market": row.get("market"),
                    "industry": "ALL",
                    "score": float(row.get("three_party_net_shares") or 0.0),
                    "description": "候選清單三大法人淨流入合計",
                }
            )
    return rows


def build_recommendations(
    stock_alpha: pd.DataFrame,
    sector_alpha: pd.DataFrame,
    sector_flow: pd.DataFrame | None = None,
    moneydj_sector_indicators: pd.DataFrame | None = None,
    finmind_composite_indicators: pd.DataFrame | None = None,
    *,
    per_sector: int = 5,
    top_n: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sector_flow_df = sector_flow if sector_flow is not None else pd.DataFrame()
    breakdown = build_stock_alpha_breakdown(
        stock_alpha,
        sector_alpha,
        sector_flow_df,
        moneydj_sector_indicators,
        finmind_composite_indicators,
    )
    if breakdown.empty:
        return pd.DataFrame(), pd.DataFrame()

    candidates = breakdown[~breakdown["is_excluded"].astype(bool)].copy()
    if candidates.empty:
        sector_context = _build_sector_context(sector_alpha, sector_flow_df)
        return pd.DataFrame(), pd.DataFrame(_summary_rows(sector_context, candidates))

    candidates = candidates.sort_values("alpha_score_total", ascending=False).copy()
    candidates["overall_rank"] = range(1, len(candidates) + 1)
    candidates["rank_in_industry"] = (
        candidates.groupby(["market", "industry"], dropna=False)["alpha_score_total"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    selected = candidates[(candidates["overall_rank"] <= top_n) | (candidates["rank_in_industry"] <= per_sector)].copy()
    reason_cols = selected.apply(_reason_text, axis=1, result_type="expand")
    reason_cols.columns = ["summary", "reason_1", "reason_2", "reason_3", "main_risk"]
    selected = pd.concat([selected.reset_index(drop=True), reason_cols.reset_index(drop=True)], axis=1)
    selected["model_win_rate"] = pd.NA
    selected["model_max_drawdown"] = pd.NA
    selected["backtest_status"] = "資料不足"
    selected["is_top_overall"] = selected["overall_rank"] <= top_n

    sector_context = _build_sector_context(sector_alpha, sector_flow_df)
    summary = pd.DataFrame(_summary_rows(sector_context, candidates))
    return selected.reset_index(drop=True), summary
