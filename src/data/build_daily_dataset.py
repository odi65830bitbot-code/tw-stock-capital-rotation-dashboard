from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from . import data_quality
from .normalize_tpex import (
    normalize_tpex_indices,
    normalize_tpex_daily_price,
    normalize_tpex_institutional_amount,
    normalize_tpex_institutional_flow,
    normalize_tpex_sector_classification,
)
from .normalize_twse import (
    normalize_twse_indices,
    normalize_twse_daily_price,
    normalize_twse_institutional_amount,
    normalize_twse_institutional_flow,
    normalize_twse_sector_classification,
)
from ..analysis.alpha_scores import compute_sector_alpha, compute_stock_alpha
from .tpex_client import TPEXClient
from .twse_client import TWSEClient
from .moneydj_client import MoneyDJClient
from .finmind_client import FinMindClient
from ..analysis.recommendations import build_recommendations, build_stock_alpha_breakdown
from ..backtest.backtest import run_recommendation_backtests

LOGGER = logging.getLogger("build_daily_dataset")


def _to_date(s: str | None) -> date:
    if not s:
        return date.today()
    if len(s) == 7 and s.isdigit():
        # 1150607
        return date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:7]))
    if len(s) == 8 and s.isdigit():
        return date.fromisoformat(f"{s[:4]}-{s[4:6]}-{s[6:8]}")
    raise ValueError("日期格式必須為 YYYYMMDD 或 R.O.C. 1150607")


def _safe_fetch(callable_obj, label: str):
    try:
        return callable_obj()
    except Exception as exc:
        LOGGER.error("%s 失敗: %s", label, exc)
        return None


def _concat_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    clean = [
        df.dropna(axis=1, how="all")
        for df in frames
        if not df.empty and not df.dropna(how="all").empty
    ]
    return pd.concat(clean, ignore_index=True) if clean else pd.DataFrame()


def _safe_merge_sector(df: pd.DataFrame, sector_map: Dict[str, str]) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    with_sector = df.copy()
    with_sector["industry"] = with_sector["stock_code"].map(sector_map)
    with_sector["industry"] = with_sector["industry"].fillna("UNKNOWN")
    return with_sector


def _infer_sector_map(twse_sector_df: pd.DataFrame, tpex_sector_df: pd.DataFrame) -> Dict[str, str]:
    twse_map = twse_sector_df.dropna(subset=["stock_code", "industry"]).set_index("stock_code")["industry"].to_dict()
    tpex_map = tpex_sector_df.dropna(subset=["stock_code", "industry"]).set_index("stock_code")["industry"].to_dict()
    sector_map = {**twse_map, **tpex_map}
    return {k: v for k, v in sector_map.items() if k}


def _sector_merge_key(value: str) -> str:
    text = str(value or "").strip()
    aliases = {
        "水泥工業": "水泥",
        "食品工業": "食品",
        "塑膠工業": "塑膠",
        "化學工業": "化工",
        "電器電纜": "電器電纜",
        "電機機械": "電機機械",
    }
    if text in aliases:
        return aliases[text]
    for suffix in ("產業", "工業", "業"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text


def _merge_moneydj_sector_flow(sector_flow_df: pd.DataFrame, moneydj_records: list[dict]) -> pd.DataFrame:
    if sector_flow_df.empty or not moneydj_records:
        return sector_flow_df
    supplement = pd.DataFrame(moneydj_records)
    if supplement.empty:
        return sector_flow_df

    out = sector_flow_df.copy()
    out["_industry_key"] = out["industry"].map(_sector_merge_key)
    supplement["_industry_key"] = supplement["industry"].map(_sector_merge_key)
    supplement["trade_date"] = pd.to_datetime(supplement["trade_date"], errors="coerce")
    supplement = supplement[
        [
            "trade_date",
            "market",
            "_industry_key",
            "moneydj_flow_rate_pct",
            "moneydj_history_points",
            "moneydj_history_latest_flow_rate_pct",
            "moneydj_flow_rate_5d_avg_pct",
            "moneydj_flow_rate_20d_avg_pct",
            "moneydj_flow_rate_accel_pct",
            "moneydj_flow_rate_5d_change_pct",
            "moneydj_sector_return_20d_pct",
            "moneydj_market_return_20d_pct",
            "moneydj_relative_strength_20d_pct",
            "moneydj_validation_status",
            "moneydj_validation_message",
            "source",
            "source_url",
        ]
    ].rename(
        columns={
            "source": "moneydj_source",
            "source_url": "moneydj_source_url",
        }
    )

    out = out.merge(
        supplement,
        on=["trade_date", "market", "_industry_key"],
        how="left",
    )
    return out.drop(columns=["_industry_key"])


def _moneydj_quality_check(records: list[dict[str, Any]], history_records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "name": "moneydj_supplemental_quality",
            "status": "warning",
            "message": "MoneyDJ 補充資料未取得",
            "details": {"rows": 0, "history_rows": len(history_records)},
        }

    rows = len(records)
    history_rows = len(history_records)
    pass_rows = sum(1 for row in records if row.get("moneydj_validation_status") == "pass")
    with_history = sum(1 for row in records if int(row.get("moneydj_history_points") or 0) >= 20)
    pass_ratio = pass_rows / rows if rows else 0.0
    history_ratio = with_history / rows if rows else 0.0
    status = "pass" if pass_ratio >= 0.9 and history_ratio >= 0.9 else "warning"
    return {
        "name": "moneydj_supplemental_quality",
        "status": status,
        "message": f"MoneyDJ 補充指標 {rows} 類股，歷史明細 {history_rows} 筆，驗證通過率 {pass_ratio:.2%}",
        "details": {
            "rows": rows,
            "history_rows": history_rows,
            "validation_pass_ratio": pass_ratio,
            "history_coverage_ratio": history_ratio,
        },
    }


def build_dataset(target_date: date, *, raw_root: Path, processed_root: Path, quality_path: Path) -> Dict[str, pd.DataFrame]:
    twse = TWSEClient(raw_root=raw_root)
    tpex = TPEXClient(raw_root=raw_root)
    moneydj = MoneyDJClient(raw_root=raw_root)
    finmind = FinMindClient(raw_root=raw_root)

    twse_raw = {
        "daily_price": _safe_fetch(lambda: twse.fetch_daily_price(target_date), "TWSE daily price"),
        "institutional_flow": _safe_fetch(lambda: twse.fetch_institutional_flow(target_date), "TWSE institutional flow"),
        "institutional_amount": _safe_fetch(lambda: twse.fetch_institutional_amount(target_date), "TWSE institutional amount"),
        "sector_classification": _safe_fetch(lambda: twse.fetch_sector_classification(target_date), "TWSE sector"),
        "index": _safe_fetch(lambda: twse.fetch_index(target_date), "TWSE index"),
    }
    tpex_raw = {
        "daily_price": _safe_fetch(lambda: tpex.fetch_daily_price(target_date), "TPEX daily price"),
        "institutional_flow": _safe_fetch(lambda: tpex.fetch_institutional_flow(target_date), "TPEX institutional flow"),
        "institutional_amount": _safe_fetch(lambda: tpex.fetch_institutional_amount(target_date), "TPEX institutional amount"),
        "sector_classification": _safe_fetch(lambda: tpex.fetch_sector_classification(target_date), "TPEX sector"),
        "index": _safe_fetch(lambda: tpex.fetch_index(target_date), "TPEX index"),
        "index_50": _safe_fetch(lambda: tpex.fetch_index_50(target_date), "TPEX 50 index"),
    }
    supplemental_raw = {
        "moneydj_market_fund_flow": _safe_fetch(
            lambda: moneydj.fetch_market_fund_flow(target_date),
            "MoneyDJ market fund flow",
        )
    }

    # normalize
    daily_frames = []
    flow_frames = []
    amount_frames = []
    index_frames = []
    sector_frames = []

    if twse_raw["daily_price"] is not None:
        daily_frames.append(normalize_twse_daily_price(twse_raw["daily_price"].records))
    if tpex_raw["daily_price"] is not None:
        daily_frames.append(normalize_tpex_daily_price(tpex_raw["daily_price"].records))

    if twse_raw["institutional_flow"] is not None:
        flow_frames.append(normalize_twse_institutional_flow(twse_raw["institutional_flow"].records))
    if tpex_raw["institutional_flow"] is not None:
        flow_frames.append(normalize_tpex_institutional_flow(tpex_raw["institutional_flow"].records))

    if twse_raw["institutional_amount"] is not None:
        amount_frames.append(normalize_twse_institutional_amount(twse_raw["institutional_amount"].records))
    if tpex_raw["institutional_amount"] is not None:
        amount_frames.append(normalize_tpex_institutional_amount(tpex_raw["institutional_amount"].records))

    if twse_raw["sector_classification"] is not None:
        sector_frames.append(normalize_twse_sector_classification(twse_raw["sector_classification"].records))
    if tpex_raw["sector_classification"] is not None:
        sector_frames.append(normalize_tpex_sector_classification(tpex_raw["sector_classification"].records))
    if twse_raw["index"] is not None:
        index_frames.append(normalize_twse_indices(twse_raw["index"].records))
    if tpex_raw["index"] is not None:
        index_frames.append(normalize_tpex_indices(tpex_raw["index"].records))
    if tpex_raw["index_50"] is not None:
        index_frames.append(
            normalize_tpex_indices(tpex_raw["index_50"].records).assign(index_name="TPEx50Index")
        )

    daily_price_df = _concat_frames(daily_frames)
    institutional_flow_df = _concat_frames(flow_frames)
    institutional_amount_df = _concat_frames(amount_frames)
    sector_df = _concat_frames(sector_frames)
    index_df = _concat_frames(index_frames)

    # --- Synthesize sector classifications for ETFs, ETNs, REITs, DRs ---
    if not daily_price_df.empty:
        existing_codes = set(sector_df["stock_code"].astype(str)) if not sector_df.empty else set()
        synthesized_sectors = []
        for _, row in daily_price_df.drop_duplicates(subset=["stock_code"]).iterrows():
            code = str(row["stock_code"])
            if code in existing_codes:
                continue
            name = str(row.get("stock_name", "")).upper()
            industry = None
            if code.startswith("00") or "ETF" in name:
                industry = "ETF"
            elif code.startswith("01"):
                industry = "REITs"
            elif code.startswith("02") or "ETN" in name:
                industry = "ETN"
            elif code.startswith("91") or "-DR" in name:
                industry = "DR(存託憑證)"
                
            if industry:
                synthesized_sectors.append({
                    "trade_date": row.get("trade_date"),
                    "market": row.get("market"),
                    "industry": industry,
                    "stock_code": code,
                    "stock_name": row.get("stock_name"),
                })
        
        if synthesized_sectors:
            syn_df = pd.DataFrame(synthesized_sectors)
            if sector_df.empty:
                sector_df = syn_df
            else:
                sector_df = pd.concat([sector_df, syn_df], ignore_index=True)
    # ---------------------------------------------------------------------

    # sector mapping
    sector_map = _infer_sector_map(
        sector_df[sector_df["market"] == "TWSE"] if not sector_df.empty else pd.DataFrame(),
        sector_df[sector_df["market"] == "TPEX"] if not sector_df.empty else pd.DataFrame(),
    )

    flow_with_sector = _safe_merge_sector(institutional_flow_df, sector_map) if not institutional_flow_df.empty else institutional_flow_df

    # sector flow parquet
    if flow_with_sector.empty:
        sector_flow_df = pd.DataFrame()
    else:
        sector_flow_df = (
            flow_with_sector.groupby(["trade_date", "market", "industry"], dropna=False)
            .agg(
                three_party_net_shares=("three_party_net_shares", lambda s: s.sum(min_count=1)),
                stock_count=("stock_code", "nunique"),
            )
            .reset_index()
        )
    moneydj_result = supplemental_raw["moneydj_market_fund_flow"]
    if moneydj_result is not None:
        sector_flow_df = _merge_moneydj_sector_flow(sector_flow_df, moneydj_result.records)
    moneydj_indicator_df = (
        pd.DataFrame(moneydj_result.records)
        if moneydj_result is not None
        else pd.DataFrame()
    )
    finmind_indicator_df = finmind.fetch_composite_indicators(target_date)

    stock_alpha_df = compute_stock_alpha(daily_price_df, institutional_flow_df, sector_df)
    if not stock_alpha_df.empty:
        stock_alpha_df = stock_alpha_df.rename(columns={"stock_alpha_score": "stock_alpha_score"})
        stock_alpha_df["alpha_score"] = stock_alpha_df["stock_alpha_score"]
    sector_alpha_df = compute_sector_alpha(stock_alpha_df)
    stock_alpha_breakdown_df = build_stock_alpha_breakdown(
        stock_alpha_df,
        sector_alpha_df,
        sector_flow_df,
        moneydj_indicator_df,
        finmind_indicator_df,
    )
    recommendations_df, recommendation_summary_df = build_recommendations(
        stock_alpha_df,
        sector_alpha_df,
        sector_flow_df,
        moneydj_indicator_df,
        finmind_indicator_df,
        per_sector=5,
        top_n=10,
    )
    recommendation_backtest_df = run_recommendation_backtests(
        daily_price_df,
        stock_alpha_breakdown_df,
        index_df,
        top_ns=(10, 20),
    )

    # 輸出 processed parquet
    processed_root.mkdir(parents=True, exist_ok=True)
    daily_price_df.to_parquet(processed_root / "daily_price.parquet", index=False)
    institutional_flow_df.to_parquet(processed_root / "institutional_flow.parquet", index=False)
    institutional_amount_df.to_parquet(processed_root / "institutional_amount.parquet", index=False)
    sector_flow_df.to_parquet(processed_root / "sector_flow.parquet", index=False)
    stock_alpha_df.to_parquet(processed_root / "stock_alpha.parquet", index=False)
    sector_alpha_df.to_parquet(processed_root / "sector_alpha.parquet", index=False)
    index_df.to_parquet(processed_root / "index.parquet", index=False)
    sector_df.to_parquet(processed_root / "sector_classification.parquet", index=False)
    moneydj_indicator_df.to_parquet(processed_root / "moneydj_sector_indicators.parquet", index=False)
    finmind_indicator_df.to_parquet(processed_root / "finmind_composite_indicators.parquet", index=False)
    stock_alpha_breakdown_df.to_parquet(processed_root / "stock_alpha_breakdown.parquet", index=False)
    recommendations_df.to_parquet(processed_root / "recommendations.parquet", index=False)
    recommendation_summary_df.to_parquet(processed_root / "recommendation_summary.parquet", index=False)
    recommendation_backtest_df.to_parquet(processed_root / "recommendation_backtest.parquet", index=False)

    quality_payload = data_quality.run_data_quality_checks(
        {
            "daily_price": daily_price_df,
            "institutional_flow": institutional_flow_df,
            "institutional_amount": institutional_amount_df,
            "sector_classification": sector_df,
            "sector_flow": sector_flow_df,
        },
        expected_date=target_date,
    )
    quality_payload["raw_sources"] = {
        "twse": {k: (v.raw_json_path.name if v else None) for k, v in twse_raw.items()},
        "tpex": {k: (v.raw_json_path.name if v else None) for k, v in tpex_raw.items()},
        "supplemental": {
            "moneydj": {
                k: (v.raw_json_path.name if v else None)
                for k, v in supplemental_raw.items()
            },
            "finmind": {
                "enabled": bool(finmind.enabled),
                "indicator_rows": int(len(finmind_indicator_df)),
            },
        },
    }
    quality_payload["source_policy"] = {
        "primary": ["TWSE official OpenAPI/CSV", "TPEX official OpenAPI/CSV"],
        "supplemental_only": ["MoneyDJ", "FinMind"],
        "note": "MoneyDJ and FinMind are stored and displayed only as supplemental context; they do not replace failed official data.",
    }
    if moneydj_result is not None:
        moneydj_check = _moneydj_quality_check(moneydj_result.records, moneydj_result.history_records)
    else:
        moneydj_check = _moneydj_quality_check([], [])
    quality_payload["checks"].append(moneydj_check)
    if quality_payload["status"] == "pass" and moneydj_check["status"] == "warning":
        quality_payload["status"] = "warning"
    quality_payload["checks"].append(
        {
            "name": "recommendation_engine",
            "status": "pass" if not recommendations_df.empty else "warning",
            "message": (
                f"推薦引擎候選清單 {len(recommendations_df)} 筆，"
                f"Alpha 拆解 {len(stock_alpha_breakdown_df)} 筆"
            ),
            "details": {
                "recommendation_rows": int(len(recommendations_df)),
                "alpha_breakdown_rows": int(len(stock_alpha_breakdown_df)),
                "backtest_rows": int(len(recommendation_backtest_df)),
                "revenue_data_available": bool(not finmind_indicator_df.empty and "finmind_revenue_yoy_pct" in finmind_indicator_df.columns),
                "financial_quality_data_available": bool(
                    not finmind_indicator_df.empty
                    and any(c in finmind_indicator_df.columns for c in ["finmind_per", "finmind_pbr", "finmind_dividend_yield_pct"])
                ),
                "finmind_indicator_rows": int(len(finmind_indicator_df)),
                "disposition_data_available": False,
                "full_delivery_data_available": False,
                "note": "FinMind 用於月營收、PER/PBR 與殖利率補充指標；處置股與全額交割股尚未接入官方公告日資料。",
            },
        }
    )
    if recommendations_df.empty and quality_payload["status"] == "pass":
        quality_payload["status"] = "warning"
    data_quality.write_data_quality_report(quality_payload, quality_path)

    return {
        "daily_price": daily_price_df,
        "institutional_flow": institutional_flow_df,
        "institutional_amount": institutional_amount_df,
        "sector_flow": sector_flow_df,
        "stock_alpha": stock_alpha_df,
        "stock_alpha_breakdown": stock_alpha_breakdown_df,
        "sector_alpha": sector_alpha_df,
        "sector_classification": sector_df,
        "moneydj_sector_indicators": moneydj_indicator_df,
        "finmind_composite_indicators": finmind_indicator_df,
        "recommendations": recommendations_df,
        "recommendation_summary": recommendation_summary_df,
        "recommendation_backtest": recommendation_backtest_df,
        "quality": quality_payload,
        "index": index_df,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build TWSE + TPEX data pipeline")
    parser.add_argument("--date", default=None, help="交易日，支援 YYYYMMDD 或 1150605")
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--processed-root", default="data/processed")
    parser.add_argument("--quality", default="data_quality_report.json")
    args = parser.parse_args()

    target = _to_date(args.date)
    LOGGER.setLevel(logging.INFO)
    logging.basicConfig(level=logging.INFO)

    result = build_dataset(
        target,
        raw_root=Path(args.raw_root),
        processed_root=Path(args.processed_root),
        quality_path=Path(args.quality),
    )

    LOGGER.info("已輸出: %s", result.keys())


if __name__ == "__main__":
    main()
