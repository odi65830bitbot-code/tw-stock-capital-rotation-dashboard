from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtest.backtest import run_recommendation_backtests
from src.data.build_daily_dataset import _to_date, build_dataset
from src.data.trading_calendar import latest_complete_trade_date
from src.modules.trend_builder import write_top_recommendation_trends


LOGGER = logging.getLogger("update_daily")
TAIPEI_TZ = ZoneInfo("Asia/Taipei")
MARKET_DATA_READY_TIME = time(20, 30)

MERGE_KEYS: dict[str, list[str]] = {
    "daily_price": ["trade_date", "market", "stock_code"],
    "institutional_flow": ["trade_date", "market", "stock_code"],
    "institutional_amount": ["trade_date", "market"],
    "sector_flow": ["trade_date", "market", "industry"],
    "stock_alpha": ["trade_date", "market", "stock_code"],
    "stock_alpha_breakdown": ["trade_date", "market", "stock_code"],
    "sector_alpha": ["trade_date", "market", "industry"],
    "sector_classification": ["market", "stock_code"],
    "moneydj_sector_indicators": ["trade_date", "market", "industry"],
    "finmind_composite_indicators": ["stock_code"],
    "recommendations": ["trade_date", "market", "stock_code"],
    "index": ["trade_date", "market", "index_name"],
}


def _previous_weekday(d: date) -> date:
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _default_target_date(now: datetime | None = None) -> date:
    local_now = now.astimezone(TAIPEI_TZ) if now else datetime.now(TAIPEI_TZ)
    target = local_now.date()
    if target.weekday() >= 5 or local_now.time() < MARKET_DATA_READY_TIME:
        target -= timedelta(days=1)
    return _previous_weekday(target)


def _setup_logging(logs_root: Path, target_date: date) -> Path:
    logs_root.mkdir(parents=True, exist_ok=True)
    log_path = logs_root / f"update_{target_date:%Y%m%d}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )
    return log_path


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


def _records(
    df: pd.DataFrame,
    *,
    latest_only: bool = True,
    as_of_date: pd.Timestamp | None = None,
) -> list[dict[str, Any]]:
    if df.empty:
        return []
    out = df.copy()
    if latest_only and "trade_date" in out.columns:
        out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce")
        latest = pd.to_datetime(as_of_date) if as_of_date is not None else out["trade_date"].max()
        out = out[out["trade_date"] == latest].copy()
    if "trade_date" in out.columns:
        out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return [
        {str(k): _json_ready(v) for k, v in row.items()}
        for row in out.replace({pd.NA: None}).to_dict(orient="records")
    ]


def _merge_frame(existing: pd.DataFrame, incoming: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if incoming.empty:
        return existing.copy()
    if existing.empty:
        merged = incoming.copy()
    else:
        merged = pd.concat([existing, incoming], ignore_index=True)
    for col in keys:
        if col not in merged.columns:
            merged[col] = pd.NA
    if "trade_date" in merged.columns:
        merged["trade_date"] = pd.to_datetime(merged["trade_date"], errors="coerce")
    merged = merged.drop_duplicates(keys, keep="last")
    sort_cols = [c for c in ["trade_date", "market", "stock_code", "industry", "index_name"] if c in merged.columns]
    if sort_cols:
        merged = merged.sort_values(sort_cols)
    return merged.reset_index(drop=True)


def _merge_processed(tmp_root: Path, processed_root: Path) -> None:
    processed_root.mkdir(parents=True, exist_ok=True)
    for name, keys in MERGE_KEYS.items():
        incoming_path = tmp_root / f"{name}.parquet"
        if not incoming_path.exists():
            LOGGER.warning("skip missing processed output: %s", incoming_path)
            continue
        incoming = pd.read_parquet(incoming_path)
        existing_path = processed_root / f"{name}.parquet"
        existing = pd.read_parquet(existing_path) if existing_path.exists() else pd.DataFrame()
        merged = _merge_frame(existing, incoming, keys)
        merged.to_parquet(existing_path, index=False)
        LOGGER.info("merged %s rows=%s", name, len(merged))

    daily = pd.read_parquet(processed_root / "daily_price.parquet")
    scores = pd.read_parquet(processed_root / "stock_alpha_breakdown.parquet")
    index_df = pd.read_parquet(processed_root / "index.parquet")
    backtest = run_recommendation_backtests(daily, scores, index_df, top_ns=(10, 20))
    backtest.to_parquet(processed_root / "recommendation_backtest.parquet", index=False)

    for latest_only_name in ["recommendation_summary"]:
        src = tmp_root / f"{latest_only_name}.parquet"
        if src.exists():
            shutil.copy2(src, processed_root / f"{latest_only_name}.parquet")


def _write_public_json(processed_root: Path, public_root: Path) -> None:
    data_dir = public_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    index_df = pd.read_parquet(processed_root / "index.parquet")
    sector = pd.read_parquet(processed_root / "sector_flow.parquet")
    stock_alpha = pd.read_parquet(processed_root / "stock_alpha_breakdown.parquet")
    recommendations = pd.read_parquet(processed_root / "recommendations.parquet")
    daily_price = pd.read_parquet(processed_root / "daily_price.parquet")
    as_of_date = latest_complete_trade_date(daily_price)
    sector_as_of_date = latest_complete_trade_date(sector)
    if sector_as_of_date is None and not sector.empty and "trade_date" in sector.columns:
        sector_as_of_date = pd.to_datetime(sector["trade_date"], errors="coerce").max()
    stock_detail_date = sector_as_of_date if sector_as_of_date is not None else as_of_date
    sector_constituents_cols = [
        c
        for c in [
            "trade_date",
            "market",
            "industry",
            "stock_code",
            "stock_name",
            "close",
            "change",
            "change_pct",
            "trade_volume",
            "trade_value_twd",
            "foreign_buy_shares",
            "foreign_sell_shares",
            "foreign_net_shares",
            "trustee_net_shares",
            "dealer_net_shares",
            "three_party_net_shares",
            "flow_rate",
            "alpha_score_total",
            "suggested_status",
        ]
        if c in stock_alpha.columns
    ]
    sector_constituents = stock_alpha[sector_constituents_cols].copy()
    if not sector_constituents.empty and "three_party_net_shares" in sector_constituents.columns:
        sector_constituents["three_party_net_shares"] = pd.to_numeric(
            sector_constituents["three_party_net_shares"], errors="coerce"
        )
        sector_constituents = sector_constituents.sort_values(
            ["market", "industry", "three_party_net_shares", "trade_value_twd"],
            ascending=[True, True, False, False],
            na_position="last",
        )

    outputs = {
        "market_latest.json": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "as_of_date": _json_ready(as_of_date),
            "records": _records(index_df, as_of_date=as_of_date),
        },
        "sector_latest.json": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "as_of_date": _json_ready(sector_as_of_date),
            "records": _records(sector, as_of_date=sector_as_of_date),
        },
        "stock_alpha_latest.json": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "as_of_date": _json_ready(as_of_date),
            "records": _records(
                stock_alpha[
                    [
                        c
                        for c in [
                            "trade_date",
                            "market",
                            "stock_code",
                            "stock_name",
                            "industry",
                            "close",
                            "trade_value_twd",
                            "alpha_score_total",
                            "main_buy_component",
                            "foreign_component",
                            "trust_component",
                            "revenue_component",
                            "quality_component",
                            "finmind_revenue_yoy_pct",
                            "finmind_revenue_mom_pct",
                            "finmind_per",
                            "finmind_pbr",
                            "finmind_dividend_yield_pct",
                            "risk_penalty",
                            "suggested_status",
                        ]
                        if c in stock_alpha.columns
                    ]
                ]
                ,
                as_of_date=as_of_date,
            ),
        },
        "sector_constituents_latest.json": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "as_of_date": _json_ready(stock_detail_date),
            "records": _records(sector_constituents, as_of_date=stock_detail_date),
        },
        "recommendations_latest.json": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "as_of_date": _json_ready(as_of_date),
            "records": _records(recommendations, as_of_date=as_of_date),
        },
    }
    for filename, payload in outputs.items():
        (data_dir / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        LOGGER.info("wrote public/data/%s", filename)

    trend_paths = write_top_recommendation_trends(
        processed_root=processed_root,
        public_root=public_root,
        top_n=10,
    )
    LOGGER.info("wrote %s recommendation trend files", len(trend_paths))


def run_update(
    *,
    target_date: date,
    raw_root: Path = ROOT / "data" / "raw",
    processed_root: Path = ROOT / "data" / "processed",
    public_root: Path = ROOT / "public",
    quality_path: Path = ROOT / "data_quality_report.json",
    logs_root: Path = ROOT / "logs",
    reports_root: Path = ROOT / "reports",
) -> dict[str, Any]:
    log_path = _setup_logging(logs_root, target_date)
    tmp_root = processed_root / "_daily_update_tmp"
    tmp_quality = tmp_root / "data_quality_report.json"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True, exist_ok=True)

    LOGGER.info("daily update started target_date=%s", target_date)
    result = build_dataset(
        target_date,
        raw_root=raw_root,
        processed_root=tmp_root,
        quality_path=tmp_quality,
    )
    _merge_processed(tmp_root, processed_root)
    _write_public_json(processed_root, public_root)

    quality = json.loads(tmp_quality.read_text(encoding="utf-8")) if tmp_quality.exists() else {}
    quality["daily_update"] = {
        "target_date": target_date.isoformat(),
        "log_path": str(log_path),
        "public_data_root": str(public_root / "data"),
        "trend_scope": "recommendation_top_10_only",
    }
    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")

    reports_root.mkdir(parents=True, exist_ok=True)
    report_path = reports_root / f"update_{target_date:%Y%m%d}.json"
    summary = {
        "target_date": target_date.isoformat(),
        "status": quality.get("status", "unknown"),
        "log_path": str(log_path),
        "processed_outputs": sorted(p.name for p in processed_root.glob("*.parquet")),
        "public_outputs": sorted(str(p.relative_to(public_root)) for p in (public_root / "data").glob("*.json")),
        "trend_files": sorted(str(p.relative_to(public_root)) for p in (public_root / "data" / "trends").glob("*.json")),
        "result_keys": sorted(result.keys()),
    }
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGGER.info("daily update finished status=%s report=%s", summary["status"], report_path)
    shutil.rmtree(tmp_root, ignore_errors=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run official-first daily Taiwan stock update")
    parser.add_argument("--date", default=None, help="交易日，支援 YYYYMMDD 或民國 1150605")
    args = parser.parse_args()
    target = _to_date(args.date) if args.date else _default_target_date()
    summary = run_update(target_date=target)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
