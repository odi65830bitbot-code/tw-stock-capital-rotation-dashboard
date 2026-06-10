from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd


@dataclass
class QualityCheckResult:
    name: str
    status: str  # pass / warning / fail
    message: str
    details: Dict[str, Any]


def _to_date_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series([], dtype="datetime64[ns]")
    return pd.to_datetime(df[col], errors="coerce")


def check_recent_trading_day(df: pd.DataFrame, date_col: str = "trade_date", expected: Optional[date] = None) -> QualityCheckResult:
    dates = _to_date_series(df, date_col).dropna()
    if dates.empty:
        return QualityCheckResult("recent_trading_date", "warning", "資料為空，無法確認交易日", {})

    latest = dates.max()
    if pd.isna(latest):
        return QualityCheckResult("recent_trading_day", "warning", "無可解析交易日", {})
    latest_date = pd.Timestamp(latest).date()

    today = expected or date.today()
    # 交易日通常不超過 target 最近 7 天
    cutoff = today - timedelta(days=7)
    if latest_date < cutoff:
        return QualityCheckResult(
            "recent_trading_date",
            "warning",
            f"最新資料日為 {latest_date}，與預期日期 {today} 間隔過大",
            {"latest_date": str(latest_date), "expected_date": str(today)},
        )
    return QualityCheckResult(
        "recent_trading_date",
        "pass",
        f"最新資料日為 {latest_date}",
        {"latest_date": str(latest_date), "expected_date": str(today)},
    )


def check_reasonable_row_count(
    df: pd.DataFrame,
    min_rows: int,
    max_rows: int,
    label: str = "",
) -> QualityCheckResult:
    rows = int(len(df))
    if rows < min_rows:
        return QualityCheckResult("reasonable_row_count", "warning", f"{label} 筆數偏少：{rows}", {"rows": rows})
    if rows > max_rows:
        return QualityCheckResult("reasonable_row_count", "warning", f"{label} 筆數偏多：{rows}", {"rows": rows})
    return QualityCheckResult("reasonable_row_count", "pass", f"{label} 筆數合理：{rows}", {"rows": rows})


def check_not_all_null(df: pd.DataFrame, columns: Iterable[str], label: str = "") -> QualityCheckResult:
    cols = [c for c in columns if c in df.columns]
    if not cols:
        return QualityCheckResult("non_null_metrics", "warning", f"{label}: 無可用欄位 {columns}", {})
    if df.empty:
        return QualityCheckResult("non_null_metrics", "fail", f"{label}: 空資料", {})
    non_null_ratio = float(df[cols].notna().any(axis=1).mean())
    if non_null_ratio == 0:
        return QualityCheckResult("non_null_metrics", "fail", f"{label}: 這些欄位全部為空", {"ratio": non_null_ratio})
    if non_null_ratio < 0.5:
        return QualityCheckResult("non_null_metrics", "warning", f"{label}: 可用資料比例偏低", {"ratio": non_null_ratio})
    return QualityCheckResult("non_null_metrics", "pass", f"{label}: 有效資料比例 {non_null_ratio:.2%}", {"ratio": non_null_ratio})


def _is_code_valid(code: str, market: str) -> bool:
    if not code:
        return False
    code = str(code).strip().upper()
    return bool(re.fullmatch(r"\d{4,6}[A-Z0-9]{0,2}$", code))


def check_stock_code_format(df: pd.DataFrame, market: str, code_col: str = "stock_code", label: str = "") -> QualityCheckResult:
    if df.empty or code_col not in df.columns:
        return QualityCheckResult("stock_code_format", "warning", f"{label}: 缺少欄位 {code_col}", {})
    valid_ratio = df[code_col].map(lambda v: _is_code_valid(str(v), market)).mean()
    if valid_ratio == 1.0:
        return QualityCheckResult("stock_code_format", "pass", f"{label}: {market} 代號格式正確率 100%", {"market": market, "valid_ratio": float(valid_ratio)})
    if valid_ratio > 0.95:
        return QualityCheckResult(
            "stock_code_format",
            "warning",
            f"{label}: {market} 代號格式正確率 {valid_ratio:.2%}",
            {"market": market, "valid_ratio": float(valid_ratio)},
        )
    return QualityCheckResult(
        "stock_code_format",
        "fail",
        f"{label}: {market} 代號格式正確率 {valid_ratio:.2%}",
        {"market": market, "valid_ratio": float(valid_ratio)},
    )


def check_market_not_mixed(df: pd.DataFrame, market: str, market_col: str = "market", label: str = "") -> QualityCheckResult:
    if df.empty or market_col not in df.columns:
        return QualityCheckResult("market_mixed_check", "warning", f"{label}: 缺少欄位 {market_col}", {})
    ratio = (df[market_col] == market).mean()
    if ratio < 0.99:
        return QualityCheckResult(
            "market_mixed_check",
            "fail",
            f"{label}: 市場欄位混雜，非 {market} 比例 {(1-ratio):.2%}",
            {"expected_market": market, "match_ratio": float(ratio)},
        )
    return QualityCheckResult("market_mixed_check", "pass", f"{label}: 市場欄位一致 ({market})", {"expected_market": market, "match_ratio": float(ratio)})


def check_market_date_alignment(
    df: pd.DataFrame,
    *,
    label: str,
    expected: Optional[date] = None,
    required_markets: tuple[str, ...] = ("TWSE", "TPEX"),
    date_col: str = "trade_date",
    market_col: str = "market",
) -> QualityCheckResult:
    if df.empty or date_col not in df.columns or market_col not in df.columns:
        return QualityCheckResult(
            "market_date_alignment",
            "warning",
            f"{label}: 缺少市場或交易日資料，無法檢查 TWSE/TPEX 是否同日",
            {},
        )

    work = df[[date_col, market_col]].copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work[market_col] = work[market_col].astype(str).str.upper()
    work = work.dropna(subset=[date_col, market_col])
    if work.empty:
        return QualityCheckResult("market_date_alignment", "warning", f"{label}: 無可解析市場交易日", {})

    latest_by_market = {
        market: work.loc[work[market_col] == market, date_col].max()
        for market in required_markets
    }
    missing = [market for market, latest in latest_by_market.items() if pd.isna(latest)]
    details = {
        "latest_by_market": {
            market: (None if pd.isna(latest) else pd.Timestamp(latest).date().isoformat())
            for market, latest in latest_by_market.items()
        },
        "expected_date": str(expected) if expected else None,
    }
    if missing:
        return QualityCheckResult(
            "market_date_alignment",
            "warning",
            f"{label}: 缺少市場資料 {', '.join(missing)}",
            details,
        )

    latest_dates = {pd.Timestamp(latest).date() for latest in latest_by_market.values()}
    if len(latest_dates) > 1:
        return QualityCheckResult(
            "market_date_alignment",
            "fail",
            f"{label}: TWSE/TPEX 最新資料日期不一致",
            details,
        )

    aligned_date = next(iter(latest_dates))
    if expected and aligned_date != expected:
        return QualityCheckResult(
            "market_date_alignment",
            "warning",
            f"{label}: TWSE/TPEX 同步日期為 {aligned_date}，但目標交易日是 {expected}",
            details,
        )

    return QualityCheckResult(
        "market_date_alignment",
        "pass",
        f"{label}: TWSE/TPEX 同步日期 {aligned_date}",
        details,
    )


def check_units(df: pd.DataFrame, amount_columns: Iterable[str], volume_columns: Iterable[str], label: str = "") -> QualityCheckResult:
    amount_cols = [c for c in amount_columns if c in df.columns]
    volume_cols = [c for c in volume_columns if c in df.columns]

    if df.empty:
        return QualityCheckResult("unit_consistency", "warning", f"{label}: 空資料", {})

    details: Dict[str, Any] = {"amount_columns": amount_cols, "volume_columns": volume_cols}
    for col in amount_cols:
        values = pd.to_numeric(df[col], errors="coerce")
        details[f"{col}_all_zero"] = bool((values.fillna(0) == 0).all())
        details[f"{col}_negative_allowed"] = bool((values < 0).any())
    for col in volume_cols:
        values = pd.to_numeric(df[col], errors="coerce")
        is_integer_like = values.dropna().apply(lambda x: float(x).is_integer()).all() if not values.empty else True
        details[f"{col}_integer_like"] = bool(is_integer_like)

    fail = False
    for k, v in details.items():
        if k.endswith("_all_zero") and v:
            fail = True
    status = "warning" if fail else "pass"
    return QualityCheckResult(
        "unit_consistency",
        status,
        f"{label}: 單位檢核完成",
        details,
    )


def run_data_quality_checks(datasets: Dict[str, pd.DataFrame], *, expected_date: Optional[date] = None) -> Dict[str, Any]:
    checks: List[QualityCheckResult] = []

    daily = datasets.get("daily_price", pd.DataFrame())
    checks.append(check_recent_trading_day(daily, "trade_date", expected=expected_date))
    checks.append(check_market_date_alignment(daily, label="daily_price", expected=expected_date))
    checks.append(check_reasonable_row_count(daily, 1, 30000, "daily_price"))
    checks.append(check_not_all_null(daily, ["trade_volume", "trade_value_twd", "close"], "daily_price"))
    daily_twse = daily[daily["market"] == "TWSE"] if "market" in daily.columns else pd.DataFrame()
    daily_tpex = daily[daily["market"] == "TPEX"] if "market" in daily.columns else pd.DataFrame()
    checks.append(check_stock_code_format(daily_twse, "TWSE", "stock_code", "daily_price"))
    checks.append(check_stock_code_format(daily_tpex, "TPEX", "stock_code", "daily_price"))
    checks.append(check_market_not_mixed(daily_twse, "TWSE", label="daily_price_twse"))
    checks.append(check_market_not_mixed(daily_tpex, "TPEX", label="daily_price_tpex"))

    flow = datasets.get("institutional_flow", pd.DataFrame())
    checks.append(check_recent_trading_day(flow, "trade_date", expected=expected_date))
    checks.append(check_market_date_alignment(flow, label="institutional_flow", expected=expected_date))
    checks.append(check_reasonable_row_count(flow, 1, 60000, "institutional_flow"))
    checks.append(check_not_all_null(flow, ["three_party_net_shares"], "institutional_flow"))
    checks.append(check_units(flow, ["three_party_net_shares"], [], "institutional_flow"))
    flow_twse = flow[flow["market"] == "TWSE"] if "market" in flow.columns else pd.DataFrame()
    flow_tpex = flow[flow["market"] == "TPEX"] if "market" in flow.columns else pd.DataFrame()
    checks.append(check_stock_code_format(flow_twse, "TWSE", "stock_code", "institutional_flow"))
    checks.append(check_stock_code_format(flow_tpex, "TPEX", "stock_code", "institutional_flow"))
    checks.append(check_market_not_mixed(flow_twse, "TWSE", market_col="market", label="institutional_flow_twse"))
    checks.append(check_market_not_mixed(flow_tpex, "TPEX", market_col="market", label="institutional_flow_tpex"))

    amount = datasets.get("institutional_amount", pd.DataFrame())
    checks.append(check_recent_trading_day(amount, "trade_date", expected=expected_date))
    checks.append(check_market_date_alignment(amount, label="institutional_amount", expected=expected_date))
    checks.append(check_reasonable_row_count(amount, 1, 100, "institutional_amount"))
    checks.append(check_not_all_null(amount, ["purchase_amount_twd", "sale_amount_twd", "net_amount_twd"], "institutional_amount"))
    checks.append(check_units(amount, ["purchase_amount_twd", "sale_amount_twd", "net_amount_twd"], [], "institutional_amount"))

    sector = datasets.get("sector_classification", pd.DataFrame())
    checks.append(check_reasonable_row_count(sector, 1, 50000, "sector_classification"))
    sector_twse = sector[sector["market"] == "TWSE"] if "market" in sector.columns else pd.DataFrame()
    sector_tpex = sector[sector["market"] == "TPEX"] if "market" in sector.columns else pd.DataFrame()
    checks.append(check_stock_code_format(sector_twse, "TWSE", "stock_code", "sector_classification"))
    checks.append(check_stock_code_format(sector_tpex, "TPEX", "stock_code", "sector_classification"))
    checks.append(check_not_all_null(sector, ["industry"], "sector_classification"))

    sector_flow = datasets.get("sector_flow", pd.DataFrame())
    checks.append(check_reasonable_row_count(sector_flow, 1, 50000, "sector_flow"))
    checks.append(check_not_all_null(sector_flow, ["three_party_net_shares"], "sector_flow"))

    overall = "pass"
    failed = [c for c in checks if c.status == "fail"]
    if failed:
        overall = "fail"
    elif any(c.status == "warning" for c in checks):
        overall = "warning"

    return {
        "generated_at": date.today().isoformat(),
        "expected_trade_date": str(expected_date or date.today()),
        "status": overall,
        "checks": [asdict(c) for c in checks],
    }


def write_data_quality_report(report: Dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
