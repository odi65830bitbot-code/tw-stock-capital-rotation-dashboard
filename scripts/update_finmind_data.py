from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.alpha_v3 import compute_alpha_v3, write_alpha_v3_outputs
from modules.backtest_factor_validator import (
    run_alpha_v3_backtest,
    validate_factor_effectiveness,
    write_backtest_outputs,
)
from modules.factor_engine_finmind import compute_finmind_factors, write_factors_outputs
from modules.finmind_client import FinMindClient
from modules.recommendation_engine_finmind import build_recommendation_observations, write_recommendations_v3
from modules.trend_builder_finmind import write_finmind_recommendation_trends

LOGGER = logging.getLogger("update_finmind_data")
ROOT = Path(__file__).resolve().parents[1]


DEFAULT_CONFIG = {
    "enabled": True,
    "request_timeout": 30,
    "retry": 3,
    "update_price_days": 370,
    "update_revenue_months": 18,
    "update_financial_quarters": 8,
    "batch_size": 20,
    "sleep_seconds": 0.5,
}


def _load_config(path: Path) -> dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    if not path.exists():
        return config
    section = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith(":"):
            section = line[:-1].strip()
            continue
        if section != "finmind" or ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        if value.lower() in {"true", "false"}:
            config[key] = value.lower() == "true"
        else:
            try:
                config[key] = int(value)
            except ValueError:
                try:
                    config[key] = float(value)
                except ValueError:
                    config[key] = value.strip('"').strip("'")
    return config


def _stock_pool(processed_root: Path, limit: int | None = None) -> list[str]:
    candidates: list[str] = []
    sector_path = processed_root / "sector_classification.parquet"
    if sector_path.exists():
        sector = pd.read_parquet(sector_path)
        if "stock_code" in sector.columns:
            candidates.extend(sector["stock_code"].astype(str).str.strip().tolist())
    if not candidates:
        daily_path = processed_root / "daily_price.parquet"
        if daily_path.exists():
            daily = pd.read_parquet(daily_path)
            if "stock_code" in daily.columns:
                daily = daily.copy()
                names = daily.get("stock_name", pd.Series("", index=daily.index)).astype(str)
                product_keywords = "ETF|ETN|元大|國泰|富邦|群益|凱基|永豐|兆豐|中信|美債|反1|正2|期|債|購|售|牛|熊"
                daily = daily[~names.str.contains(product_keywords, case=False, regex=True, na=False)]
                candidates.extend(daily["stock_code"].astype(str).str.strip().tolist())
    stocks = sorted({code for code in candidates if code and code.isdigit() and len(code) == 4})
    return stocks[:limit] if limit else stocks


def _concat(results: list[pd.DataFrame]) -> pd.DataFrame:
    clean = [df for df in results if df is not None and not df.empty]
    return pd.concat(clean, ignore_index=True) if clean else pd.DataFrame()


def _fetch_stock_dataset(
    client: FinMindClient,
    dataset: str,
    stock_ids: list[str],
    *,
    start_date: str,
    end_date: str,
    batch_size: int,
    sleep_seconds: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frames: list[pd.DataFrame] = []
    unavailable: list[str] = []
    for idx, stock_id in enumerate(stock_ids, start=1):
        result = client.fetch_dataset(
            dataset,
            stock_id=stock_id,
            start_date=start_date,
            end_date=end_date,
            allow_unavailable=True,
        )
        if result.status == "ok":
            frames.append(result.dataframe)
        elif result.status == "unavailable":
            unavailable.append(stock_id)
        if batch_size > 0 and idx % batch_size == 0:
            LOGGER.info("%s fetched %s/%s", dataset, idx, len(stock_ids))
            time.sleep(sleep_seconds)
    return _concat(frames), {"dataset": dataset, "rows": int(sum(len(df) for df in frames)), "unavailable": unavailable}


def _rename_price(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if "stock_code" not in out.columns:
        out["stock_code"] = out["stock_id"].astype(str)
    return out


def _stock_metadata(processed_root: Path, stock_info: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    sector_path = processed_root / "sector_classification.parquet"
    if sector_path.exists():
        sector = pd.read_parquet(sector_path)
        if "stock_code" in sector.columns:
            sector = sector.copy()
            sector["stock_id"] = sector["stock_code"].astype(str)
            if "industry" in sector.columns and "sector" not in sector.columns:
                sector["sector"] = sector["industry"]
            frames.append(sector[[c for c in ["stock_id", "stock_name", "market", "sector", "industry"] if c in sector.columns]])
    if not stock_info.empty and "stock_id" in stock_info.columns:
        info = stock_info.copy()
        info["stock_id"] = info["stock_id"].astype(str)
        if "stock_name" not in info.columns and "name" in info.columns:
            info["stock_name"] = info["name"]
        frames.append(info[[c for c in ["stock_id", "stock_name"] if c in info.columns]])
    if not frames:
        return pd.DataFrame(columns=["stock_id"])
    out = frames[0].drop_duplicates("stock_id", keep="last")
    for frame in frames[1:]:
        frame = frame.drop_duplicates("stock_id", keep="last")
        out = out.merge(frame, on="stock_id", how="outer", suffixes=("", "_info"))
        for col in ["stock_name", "market", "sector", "industry"]:
            info_col = f"{col}_info"
            if info_col in out.columns:
                if col in out.columns:
                    out[col] = out[col].where(out[col].notna() & out[col].astype(str).ne(""), out[info_col])
                    out = out.drop(columns=[info_col])
                else:
                    out = out.rename(columns={info_col: col})
    return out.drop_duplicates("stock_id", keep="last")


def _merge_metadata(df: pd.DataFrame, metadata: pd.DataFrame) -> pd.DataFrame:
    if df.empty or metadata.empty or "stock_id" not in df.columns:
        return df
    out = df.copy()
    meta = metadata.drop_duplicates("stock_id", keep="last").copy()
    for col in ["stock_name", "market", "sector", "industry"]:
        if col in out.columns and col in meta.columns:
            meta = meta.rename(columns={col: f"{col}_meta"})
    out = out.merge(meta, on="stock_id", how="left")
    for col in ["stock_name", "market", "sector", "industry"]:
        meta_col = f"{col}_meta"
        if meta_col in out.columns:
            if col in out.columns:
                out[col] = out[col].where(out[col].notna() & out[col].astype(str).ne(""), out[meta_col])
                out = out.drop(columns=[meta_col])
            else:
                out = out.rename(columns={meta_col: col})
    if "sector" not in out.columns and "industry" in out.columns:
        out["sector"] = out["industry"]
    if "industry" not in out.columns and "sector" in out.columns:
        out["industry"] = out["sector"]
    return out


def update_finmind_data(
    *,
    raw_root: Path,
    cache_root: Path,
    processed_root: Path,
    public_root: Path,
    config_path: Path,
    limit: int | None = None,
) -> dict[str, Any]:
    config = _load_config(config_path)
    if not bool(config.get("enabled", True)):
        raise RuntimeError("FinMind is disabled in config.yaml")
    client = FinMindClient(
        raw_root=raw_root,
        cache_root=cache_root,
        timeout=int(config["request_timeout"]),
        retry=int(config["retry"]),
        sleep_seconds=float(config["sleep_seconds"]),
    )
    if not client.enabled:
        raise RuntimeError("FINMIND_TOKEN is not configured. Put it in the shell, .env, or GitHub Actions Secrets.")

    today = date.today()
    end_date = today.isoformat()
    price_start = (pd.Timestamp(today) - pd.Timedelta(days=int(config["update_price_days"]))).strftime("%Y-%m-%d")
    revenue_start = (pd.Timestamp(today) - pd.DateOffset(months=int(config["update_revenue_months"]))).strftime("%Y-%m-%d")
    financial_start = (pd.Timestamp(today) - pd.DateOffset(months=int(config["update_financial_quarters"]) * 3)).strftime("%Y-%m-%d")

    stock_info = client.fetch_dataset("TaiwanStockInfo", start_date=price_start, end_date=end_date, allow_unavailable=True)
    metadata = _stock_metadata(processed_root, stock_info.dataframe)
    pool = _stock_pool(processed_root, limit)
    if not pool and not stock_info.dataframe.empty:
        pool = sorted(stock_info.dataframe["stock_id"].astype(str).str.strip().dropna().unique().tolist())
        pool = [code for code in pool if code.isdigit() and len(code) == 4]
        pool = pool[:limit] if limit else pool
    if not pool:
        raise RuntimeError("Cannot build FinMind stock pool. Run the official TWSE/TPEX update first.")

    quality: dict[str, Any] = {
        "generated_at": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "pass",
        "stock_pool_size": len(pool),
        "source_policy": {
            "primary": ["TWSE official OpenAPI/CSV", "TPEX official OpenAPI/CSV"],
            "supplemental_only": ["FinMind"],
            "note": "FinMind is supplemental and must not replace official daily facts.",
        },
        "datasets": [],
    }

    price, meta = _fetch_stock_dataset(
        client,
        "TaiwanStockPrice",
        pool,
        start_date=price_start,
        end_date=end_date,
        batch_size=int(config["batch_size"]),
        sleep_seconds=float(config["sleep_seconds"]),
    )
    quality["datasets"].append(meta)
    institutional, meta = _fetch_stock_dataset(
        client,
        "TaiwanStockInstitutionalInvestorsBuySell",
        pool,
        start_date=price_start,
        end_date=end_date,
        batch_size=int(config["batch_size"]),
        sleep_seconds=float(config["sleep_seconds"]),
    )
    quality["datasets"].append(meta)
    margin, meta = _fetch_stock_dataset(
        client,
        "TaiwanStockMarginPurchaseShortSale",
        pool,
        start_date=price_start,
        end_date=end_date,
        batch_size=int(config["batch_size"]),
        sleep_seconds=float(config["sleep_seconds"]),
    )
    quality["datasets"].append(meta)
    revenue, meta = _fetch_stock_dataset(
        client,
        "TaiwanStockMonthRevenue",
        pool,
        start_date=revenue_start,
        end_date=end_date,
        batch_size=int(config["batch_size"]),
        sleep_seconds=float(config["sleep_seconds"]),
    )
    quality["datasets"].append(meta)

    financial_frames: list[pd.DataFrame] = []
    for dataset in ["TaiwanStockFinancialStatements", "TaiwanStockBalanceSheet", "TaiwanStockCashFlowsStatement"]:
        df, meta = _fetch_stock_dataset(
            client,
            dataset,
            pool,
            start_date=financial_start,
            end_date=end_date,
            batch_size=int(config["batch_size"]),
            sleep_seconds=float(config["sleep_seconds"]),
        )
        if not df.empty:
            df["finmind_dataset"] = dataset
            financial_frames.append(df)
        quality["datasets"].append(meta)
    financials = _concat(financial_frames)

    optional_frames: dict[str, pd.DataFrame] = {}
    for dataset in ["TaiwanStockShareholding", "TaiwanStockSecuritiesLending", "TaiwanStockTradingDailyReport"]:
        df, meta = _fetch_stock_dataset(
            client,
            dataset,
            pool,
            start_date=price_start,
            end_date=end_date,
            batch_size=int(config["batch_size"]),
            sleep_seconds=float(config["sleep_seconds"]),
        )
        optional_frames[dataset] = df
        quality["datasets"].append(meta)

    per = client.fetch_dataset("TaiwanStockPER", start_date=price_start, end_date=end_date, allow_unavailable=True).dataframe
    quality["datasets"].append({"dataset": "TaiwanStockPER", "rows": int(len(per)), "unavailable": [] if not per.empty else ["all"]})

    processed_root.mkdir(parents=True, exist_ok=True)
    _rename_price(price).to_parquet(processed_root / "finmind_price.parquet", index=False)
    institutional.to_parquet(processed_root / "finmind_institutional.parquet", index=False)
    margin.to_parquet(processed_root / "finmind_margin.parquet", index=False)
    revenue.to_parquet(processed_root / "finmind_revenue.parquet", index=False)
    financials.to_parquet(processed_root / "finmind_financials.parquet", index=False)

    factors = compute_finmind_factors(
        price=price,
        institutional=institutional,
        margin=margin,
        revenue=revenue,
        financials=financials,
        per=per,
    )
    factors = _merge_metadata(factors, metadata)
    factor_base = factors.copy()
    factor_base.to_parquet(processed_root / "finmind_factor_base.parquet", index=False)
    write_factors_outputs(
        factors,
        processed_path=processed_root / "factors_finmind.parquet",
        public_json_path=public_root / "data" / "factors_latest.json",
    )
    alpha_v3 = compute_alpha_v3(factors)
    write_alpha_v3_outputs(
        alpha_v3,
        processed_path=processed_root / "stock_alpha_v3.parquet",
        public_json_path=public_root / "data" / "stock_alpha_v3_latest.json",
    )
    effectiveness = validate_factor_effectiveness(alpha_v3, price)
    backtest = run_alpha_v3_backtest(price, alpha_v3, top_ns=(5, 10, 20))
    recommendations_v3 = build_recommendation_observations(alpha_v3, backtest, top_n=100)
    backtest.to_parquet(processed_root / "backtest_alpha_v3.parquet", index=False)
    effectiveness.to_parquet(processed_root / "factor_effectiveness.parquet", index=False)
    write_recommendations_v3(
        recommendations_v3,
        processed_path=processed_root / "recommendations_v3.parquet",
        public_json_path=public_root / "data" / "recommendations_v3_latest.json",
    )
    write_backtest_outputs(backtest=backtest, effectiveness=effectiveness, public_root=public_root)
    trend_paths = write_finmind_recommendation_trends(processed_root=processed_root, public_root=public_root, top_n=10)

    quality["outputs"] = {
        "finmind_price": int(len(price)),
        "finmind_institutional": int(len(institutional)),
        "finmind_margin": int(len(margin)),
        "finmind_revenue": int(len(revenue)),
        "finmind_financials": int(len(financials)),
        "factors_finmind": int(len(factors)),
        "stock_alpha_v3": int(len(alpha_v3)),
        "factor_effectiveness": int(len(effectiveness)),
        "backtest_alpha_v3": int(len(backtest)),
        "recommendations_v3": int(len(recommendations_v3)),
        "trend_files": int(len(trend_paths)),
    }
    if any(len(item.get("unavailable", [])) for item in quality["datasets"]):
        quality["status"] = "warning"
    report_path = ROOT / "data_quality_report_finmind.json"
    report_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return quality


def main() -> None:
    parser = argparse.ArgumentParser(description="Update supplemental FinMind data and Alpha v3 factors")
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--cache-root", default="data/cache")
    parser.add_argument("--processed-root", default="data/processed")
    parser.add_argument("--public-root", default="public")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--limit", type=int, default=None, help="Optional stock limit for smoke testing real API calls")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        quality = update_finmind_data(
            raw_root=Path(args.raw_root),
            cache_root=Path(args.cache_root),
            processed_root=Path(args.processed_root),
            public_root=Path(args.public_root),
            config_path=Path(args.config),
            limit=args.limit,
        )
    except RuntimeError as exc:
        LOGGER.error("%s", exc)
        raise SystemExit(1) from None
    LOGGER.info("FinMind update complete: %s", quality["outputs"])


if __name__ == "__main__":
    main()
