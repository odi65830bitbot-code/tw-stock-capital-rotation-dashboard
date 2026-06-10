#!/usr/bin/env python3
"""Build formal dashboard JSON files from processed market datasets.

Frontend rule: pages only read public/data/*.json. This script is the contract
adapter between the data pipeline outputs and the dashboard.
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
PUBLIC_DATA = ROOT / "public" / "data"
QUALITY_PATH = ROOT / "data_quality_report.json"
TAIPEI = ZoneInfo("Asia/Taipei")

SECTOR_NAME_MAP = {
    "金融保險業": "銀行金融",
    "半導體業": "半導體",
    "電子零組件業": "電子零組件",
    "電腦及週邊設備業": "電腦週邊",
    "通信網路業": "通訊網路",
    "電子通路業": "電子通路",
    "資訊服務業": "資訊服務",
    "其他電子業": "其他電子",
    "光電業": "光電",
    "航運業": "航運業",
    "鋼鐵工業": "鋼鐵",
    "塑膠工業": "塑膠",
    "化學工業": "化工",
    "生技醫療業": "生技醫療",
    "建材營造業": "營建",
    "觀光餐旅": "觀光餐旅",
    "觀光事業": "觀光餐旅",
    "食品工業": "食品",
    "紡織纖維": "紡織",
    "油電燃氣業": "油電燃氣",
    "電機機械": "電機機械",
    "汽車工業": "汽車",
    "造紙工業": "造紙",
    "橡膠工業": "橡膠",
    "水泥工業": "水泥",
    "玻璃陶瓷": "玻璃陶瓷",
    "貿易百貨": "貿易百貨",
    "居家生活": "居家生活",
    "文化創意業": "文化創意",
    "數位雲端": "數位雲端",
    "綠能環保": "綠能環保",
}

NUMERIC_CANDIDATES = {
    "rank": ["rank", "ranking", "sort", "order"],
    "net_1d_yi": [
        "net_1d_yi",
        "net_buy_1d",
        "netBuy1d",
        "net_buy_1d_yi",
        "flow_1d",
        "fund_flow_1d",
        "amount_1d",
        "buy_sell_1d",
        "one_day_net_buy",
    ],
    "net_5d_yi": ["net_5d_yi", "net_buy_5d", "netBuy5d", "flow_5d", "fund_flow_5d", "amount_5d"],
    "net_20d_yi": ["net_20d_yi", "net_buy_20d", "netBuy20d", "flow_20d", "fund_flow_20d", "amount_20d"],
    "net_60d_yi": ["net_60d_yi", "net_buy_60d", "netBuy60d", "flow_60d", "amount_60d"],
    "chg_1d": ["chg_1d", "change_1d", "change_pct", "return_1d", "pct_1d", "price_change_1d"],
    "chg_5d": ["chg_5d", "change_5d", "return_5d", "pct_5d"],
    "chg_20d": ["chg_20d", "change_20d", "return_20d", "pct_20d"],
    "accel": ["accel", "flow_accel", "capital_acceleration", "moneydj_flow_rate_accel_pct"],
    "concentration": ["concentration", "flow_concentration", "capital_concentration"],
    "cp_score": ["cp_score", "cp", "value_score", "cost_performance_score"],
    "bottom_score": ["bottom_score", "bottom_fishing_score", "dip_score"],
    "alpha_score": ["alpha_score", "sector_alpha_score", "alpha", "score"],
    "stock_count": ["stock_count", "constituents", "count"],
}

NAME_CANDIDATES = ["sector_name", "sector", "industry", "name", "label", "category"]


def now_iso() -> str:
    return datetime.now(TAIPEI).replace(microsecond=0).isoformat()


def read_parquet(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(path)
    except Exception as exc:  # keep pipeline resilient; report in output status
        return pd.DataFrame({"__read_error__": [str(exc)]})


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def as_date(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        ts = pd.to_datetime(value)
        if pd.isna(ts):
            return None
        return str(ts.date())
    except Exception:
        text = str(value)
        return text[:10] if text else None


def latest_date(df: pd.DataFrame, column: str = "trade_date") -> str | None:
    if df.empty or column not in df.columns:
        return None
    values = df[column].dropna()
    if values.empty:
        return None
    return as_date(values.max())


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, str):
            cleaned = value.replace(",", "").replace("%", "").strip()
            if not cleaned or cleaned in {"-", "--", "N/A", "null", "None"}:
                return None
            value = cleaned
        num = float(value)
    except Exception:
        return None
    if math.isnan(num) or math.isinf(num):
        return None
    return num


def round_or_none(value: Any, digits: int = 2) -> float | None:
    num = to_float(value)
    if num is None:
        return None
    return round(num, digits)


def first_present(row: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def normalize_sector_name(name: Any) -> str | None:
    if name is None:
        return None
    text = str(name).strip()
    if not text:
        return None
    return SECTOR_NAME_MAP.get(text, text)


def recursively_find_record_lists(value: Any) -> list[list[dict[str, Any]]]:
    found: list[list[dict[str, Any]]] = []
    if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
        keys = set().union(*(item.keys() for item in value[:10]))
        has_name = bool(keys.intersection(NAME_CANDIDATES))
        has_metric = any(
            any(candidate in keys for candidate in candidates)
            for candidates in NUMERIC_CANDIDATES.values()
        )
        if has_name or has_metric:
            found.append(value)  # type: ignore[arg-type]
    elif isinstance(value, dict):
        for child in value.values():
            found.extend(recursively_find_record_lists(child))
    return found


def normalize_reference_sector(row: dict[str, Any], index: int) -> dict[str, Any] | None:
    name = normalize_sector_name(first_present(row, NAME_CANDIDATES))
    if not name:
        return None
    out: dict[str, Any] = {
        "rank": int(round_or_none(first_present(row, NUMERIC_CANDIDATES["rank"]), 0) or index + 1),
        "sector_name": name,
        "category": str(first_present(row, ["category", "market", "board"]) or "產業"),
        "source_record": row,
    }
    for field, candidates in NUMERIC_CANDIDATES.items():
        if field == "rank":
            continue
        out[field] = round_or_none(first_present(row, candidates), 2)
    position = first_present(row, ["position", "quadrant", "rotation_state", "state"])
    out["position"] = str(position) if position not in (None, "") else infer_position(out)
    out["source"] = first_present(row, ["source", "data_source"]) or "sectorrotation.netlify.app reference"
    return out


def extract_reference_sectors(payload: dict[str, Any]) -> list[dict[str, Any]]:
    lists: list[list[dict[str, Any]]] = []
    for key in ["sectors", "records", "items", "data", "sector_rotation", "rankings", "rows"]:
        value = payload.get(key)
        if isinstance(value, list):
            lists.append(value)  # type: ignore[arg-type]
    lists.extend(recursively_find_record_lists(payload))

    best: list[dict[str, Any]] = []
    for candidate in lists:
        normalized = []
        seen = set()
        for idx, row in enumerate(candidate):
            item = normalize_reference_sector(row, idx)
            if not item or item["sector_name"] in seen:
                continue
            seen.add(item["sector_name"])
            normalized.append(item)
        if len(normalized) > len(best):
            best = normalized
    return best


def infer_position(row: dict[str, Any]) -> str:
    net = to_float(row.get("net_20d_yi"))
    if net is None:
        net = to_float(row.get("net_5d_yi"))
    if net is None:
        net = to_float(row.get("net_1d_yi"))
    chg = to_float(row.get("chg_20d"))
    if chg is None:
        chg = to_float(row.get("chg_5d"))
    if chg is None:
        chg = to_float(row.get("chg_1d"))
    net = net or 0
    chg = chg or 0
    if net >= 0 and chg >= 0:
        return "主力"
    if net >= 0 and chg < 0:
        return "輪動"
    if net < 0 and chg >= 0:
        return "觀望"
    return "退潮"


def build_price_lookup(daily_price: pd.DataFrame) -> pd.DataFrame:
    if daily_price.empty or "stock_code" not in daily_price.columns or "close" not in daily_price.columns:
        return pd.DataFrame(columns=["stock_code", "price_date", "close", "change", "change_pct", "trade_value_twd"])
    work = daily_price.copy()
    work["price_date"] = work.get("trade_date").map(as_date) if "trade_date" in work.columns else None
    work = work.sort_values(["stock_code", "price_date"])
    cols = [col for col in ["stock_code", "stock_name", "market", "price_date", "close", "change", "change_pct", "trade_value_twd"] if col in work.columns]
    return work[cols].dropna(subset=["stock_code"]).drop_duplicates("stock_code", keep="last")


def stock_industry_lookup(*frames: pd.DataFrame) -> pd.DataFrame:
    pieces = []
    for frame in frames:
        if frame.empty or "stock_code" not in frame.columns or "industry" not in frame.columns:
            continue
        cols = [col for col in ["stock_code", "industry", "market", "stock_name"] if col in frame.columns]
        pieces.append(frame[cols].dropna(subset=["stock_code"]))
    if not pieces:
        return pd.DataFrame(columns=["stock_code", "industry"])
    out = pd.concat(pieces, ignore_index=True)
    return out.drop_duplicates("stock_code", keep="last")


def build_official_sector_records(
    sector_flow: pd.DataFrame,
    institutional_flow: pd.DataFrame,
    daily_price: pd.DataFrame,
    stock_alpha_breakdown: pd.DataFrame,
    stock_alpha: pd.DataFrame,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_meta = {
        "source": ["TWSE/TPEX official processed data", "FinMind supplemental data when available"],
        "amount_estimation_method": "institutional shares multiplied by latest available official close; exact official sector amount is not recomputed in frontend",
    }
    if sector_flow.empty or "__read_error__" in sector_flow.columns:
        return [], {**source_meta, "status": "error", "message": "sector_flow.parquet unavailable"}

    date = latest_date(sector_flow) or latest_date(institutional_flow)
    if not date:
        return [], {**source_meta, "status": "error", "message": "no trade_date in sector sources"}

    sf = sector_flow[sector_flow["trade_date"].map(as_date) == date].copy() if "trade_date" in sector_flow.columns else sector_flow.copy()
    if sf.empty:
        return [], {**source_meta, "status": "error", "message": "no sector rows on latest date"}

    price_lookup = build_price_lookup(daily_price)
    industry_lookup = stock_industry_lookup(stock_alpha_breakdown, stock_alpha)
    amount_by_sector: dict[str, float] = {}
    change_by_sector: dict[str, float] = {}
    trade_value_by_sector: dict[str, float] = {}

    if not institutional_flow.empty and "stock_code" in institutional_flow.columns:
        inst = institutional_flow[institutional_flow["trade_date"].map(as_date) == date].copy() if "trade_date" in institutional_flow.columns else institutional_flow.copy()
        if not inst.empty:
            inst = inst.merge(price_lookup, on="stock_code", how="left", suffixes=("", "_price"))
            inst = inst.merge(industry_lookup[["stock_code", "industry"]], on="stock_code", how="left") if not industry_lookup.empty else inst
            if "three_party_net_shares" in inst.columns and "close" in inst.columns:
                inst["amount_yi"] = pd.to_numeric(inst["three_party_net_shares"], errors="coerce") * pd.to_numeric(inst["close"], errors="coerce") / 100_000_000
                inst["sector_name"] = inst.get("industry", "未分類").map(normalize_sector_name)
                amount_by_sector = inst.dropna(subset=["sector_name"]).groupby("sector_name")["amount_yi"].sum().to_dict()
            if "change_pct" in inst.columns:
                inst["sector_name"] = inst.get("industry", "未分類").map(normalize_sector_name)
                change_by_sector = inst.dropna(subset=["sector_name"]).groupby("sector_name")["change_pct"].mean().to_dict()
            if "trade_value_twd" in inst.columns:
                inst["sector_name"] = inst.get("industry", "未分類").map(normalize_sector_name)
                trade_value_by_sector = inst.dropna(subset=["sector_name"]).groupby("sector_name")["trade_value_twd"].sum().to_dict()

    records: list[dict[str, Any]] = []
    for _, row in sf.iterrows():
        raw_name = row.get("industry") or row.get("sector_name") or row.get("name")
        name = normalize_sector_name(raw_name)
        if not name:
            continue
        net_shares = to_float(row.get("three_party_net_shares"))
        flow_rate_5d = to_float(row.get("moneydj_flow_rate_5d_avg_pct"))
        flow_rate_20d = to_float(row.get("moneydj_flow_rate_20d_avg_pct"))
        accel = to_float(row.get("moneydj_flow_rate_accel_pct"))
        relative_strength = to_float(row.get("moneydj_relative_strength_20d_pct"))
        chg_20d = to_float(row.get("moneydj_sector_return_20d_pct"))
        item = {
            "sector_name": name,
            "category": row.get("market") or "產業",
            "stock_count": int(to_float(row.get("stock_count")) or 0),
            "net_1d_shares": round_or_none(net_shares, 0),
            "net_1d_yi": round_or_none(amount_by_sector.get(name), 2),
            "net_5d_yi": None,
            "net_20d_yi": None,
            "net_60d_yi": None,
            "foreign_net_yi": None,
            "trust_net_yi": None,
            "dealer_net_yi": None,
            "flow_rate_5d_pct": round_or_none(flow_rate_5d, 2),
            "flow_rate_20d_pct": round_or_none(flow_rate_20d, 2),
            "accel": round_or_none(accel, 2),
            "concentration": None,
            "chg_1d": round_or_none(change_by_sector.get(name), 2),
            "chg_5d": None,
            "chg_20d": round_or_none(chg_20d, 2),
            "relative_strength_20d_pct": round_or_none(relative_strength, 2),
            "trade_value_yi": round_or_none((trade_value_by_sector.get(name) or 0) / 100_000_000, 2) if name in trade_value_by_sector else None,
            "validation_status": row.get("moneydj_validation_status") or "official_pipeline",
            "source": "TWSE/TPEX official processed data",
        }
        item["position"] = infer_position(item)
        records.append(item)

    records.sort(key=lambda r: (to_float(r.get("net_1d_yi")) is not None, to_float(r.get("net_1d_yi")) or -10**12, to_float(r.get("net_1d_shares")) or -10**12), reverse=True)
    for idx, item in enumerate(records, 1):
        item["rank"] = idx
    return records, {**source_meta, "status": "ok", "date": date}


def percentile_rank(values: list[float], value: float | None) -> float:
    clean = sorted(v for v in values if v is not None and not math.isnan(v))
    if value is None or not clean:
        return 0.0
    below = sum(1 for v in clean if v <= value)
    return below / len(clean)


def enrich_sector_scores(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    net_values = [to_float(r.get("net_5d_yi")) if to_float(r.get("net_5d_yi")) is not None else to_float(r.get("net_1d_yi")) for r in records]
    chg_values = [to_float(r.get("chg_5d")) if to_float(r.get("chg_5d")) is not None else to_float(r.get("chg_1d")) for r in records]
    accel_values = [to_float(r.get("accel")) for r in records]
    out = []
    for row in records:
        net = to_float(row.get("net_5d_yi"))
        if net is None:
            net = to_float(row.get("net_1d_yi"))
        chg = to_float(row.get("chg_5d"))
        if chg is None:
            chg = to_float(row.get("chg_1d"))
        accel = to_float(row.get("accel"))
        flow_rank = percentile_rank([v for v in net_values if v is not None], net)
        accel_rank = percentile_rank([v for v in accel_values if v is not None], accel)
        chg_abs = abs(chg or 0)
        not_overheated = max(0.0, 1.0 - min(chg_abs, 12.0) / 12.0)
        cp_score = to_float(row.get("cp_score"))
        if cp_score is None:
            cp_score = 100 * (0.58 * flow_rank + 0.22 * not_overheated + 0.20 * accel_rank)
        bottom_score = to_float(row.get("bottom_score"))
        if bottom_score is None:
            positive_flow = max(net or 0, 0)
            flow_support = percentile_rank([max(v or 0, 0) for v in net_values if v is not None], positive_flow)
            pullback = max(0.0, min(-(chg or 0), 8.0) / 8.0)
            bottom_score = 100 * (0.55 * flow_support + 0.35 * pullback + 0.10 * accel_rank)
        alpha_score = to_float(row.get("alpha_score"))
        if alpha_score is None:
            strength = percentile_rank([v for v in chg_values if v is not None], chg)
            alpha_score = 100 * (0.5 * flow_rank + 0.3 * strength + 0.2 * accel_rank)
        item = dict(row)
        item["cp_score"] = round_or_none(cp_score, 2)
        item["bottom_score"] = round_or_none(bottom_score, 2)
        item["alpha_score"] = round_or_none(alpha_score, 2)
        item["position"] = item.get("position") or infer_position(item)
        out.append(item)
    return out


def sector_rotation_payload(reference: dict[str, Any], records: list[dict[str, Any]], source_meta: dict[str, Any], data_date: str | None) -> dict[str, Any]:
    payload = dict(reference) if reference else {}
    payload.update({
        "status": "ok" if records else "error",
        "version": "sector-rotation-formal-v1",
        "data_timestamp": data_date,
        "as_of_date": data_date,
        "generated_at": now_iso(),
        "source": source_meta.get("source") or ["TWSE/TPEX official processed data", "FinMind supplemental data"],
        "source_note": source_meta.get("amount_estimation_method"),
        "records": records,
        "sectors": records,
    })
    if "market_chg_1d" not in payload:
        payload["market_chg_1d"] = first_present(reference, ["market_chg_1d", "market_change_pct", "index_change_pct", "taiex_change_pct"]) if reference else None
    if not records:
        payload["message"] = source_meta.get("message") or "資料尚未更新，請稍後再試"
    return payload


def make_cp_payload(records: list[dict[str, Any]], data_date: str | None) -> dict[str, Any]:
    ranked = sorted(records, key=lambda r: to_float(r.get("cp_score")) or -1, reverse=True)
    for idx, row in enumerate(ranked, 1):
        row["cp_rank"] = idx
    return {
        "status": "ok" if ranked else "error",
        "version": "cp-ranking-formal-v1",
        "data_timestamp": data_date,
        "as_of_date": data_date,
        "generated_at": now_iso(),
        "source": ["sector_rotation_latest.json", "TWSE/TPEX official processed data"],
        "calculation_location": "data_pipeline",
        "records": ranked,
        "items": ranked,
        "message": None if ranked else "資料尚未更新，請稍後再試",
    }


def make_bottom_payload(records: list[dict[str, Any]], data_date: str | None) -> dict[str, Any]:
    ranked = sorted(records, key=lambda r: to_float(r.get("bottom_score")) or -1, reverse=True)
    for idx, row in enumerate(ranked, 1):
        row["bottom_rank"] = idx
    return {
        "status": "ok" if ranked else "error",
        "version": "bottom-fishing-formal-v1",
        "data_timestamp": data_date,
        "as_of_date": data_date,
        "generated_at": now_iso(),
        "source": ["sector_rotation_latest.json", "TWSE/TPEX official processed data"],
        "calculation_location": "data_pipeline",
        "records": ranked,
        "items": ranked,
        "message": None if ranked else "資料尚未更新，請稍後再試",
    }


def parse_tags(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    text = str(value).strip()
    if not text or text in {"[]", "nan", "None"}:
        return []
    for sep in ["|", ",", "、", ";"]:
        if sep in text:
            return [part.strip(" []'\"") for part in text.split(sep) if part.strip(" []'\"")]
    return [text.strip(" []'\"")]


def build_stock_alpha_records(stock_alpha_breakdown: pd.DataFrame, stock_alpha: pd.DataFrame) -> tuple[list[dict[str, Any]], str | None, str]:
    source_name = "stock_alpha_breakdown.parquet"
    frame = stock_alpha_breakdown.copy()
    if frame.empty or "__read_error__" in frame.columns:
        frame = stock_alpha.copy()
        source_name = "stock_alpha.parquet"
    if frame.empty or "stock_code" not in frame.columns:
        return [], None, source_name
    data_date = latest_date(frame)
    if data_date and "trade_date" in frame.columns:
        frame = frame[frame["trade_date"].map(as_date) == data_date].copy()
    if frame.empty:
        return [], data_date, source_name

    score_col = "alpha_score_total" if "alpha_score_total" in frame.columns else "stock_alpha_score" if "stock_alpha_score" in frame.columns else "alpha_score"
    if score_col not in frame.columns:
        frame[score_col] = 0
    frame = frame.sort_values(score_col, ascending=False)

    records: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        code = str(row.get("stock_code") or "").strip()
        if not code:
            continue
        close = to_float(row.get("close"))
        net_shares = to_float(row.get("three_party_net_shares"))
        net_amount = net_shares * close / 100_000_000 if net_shares is not None and close is not None else None
        trade_value = to_float(row.get("trade_value_twd"))
        score = to_float(row.get(score_col)) or 0
        risk_tags = parse_tags(row.get("risk_flags"))
        if bool(row.get("low_liquidity")):
            risk_tags.append("低流動性")
        if bool(row.get("abnormal_volatility")):
            risk_tags.append("波動異常")
        if bool(row.get("is_disposition")):
            risk_tags.append("處置股")
        if bool(row.get("is_full_delivery")):
            risk_tags.append("全額交割")
        risk_tags = list(dict.fromkeys([tag for tag in risk_tags if tag]))
        sector = normalize_sector_name(row.get("industry")) or "未分類"
        item = {
            "rank": len(records) + 1,
            "stock_id": code,
            "stock_code": code,
            "stock_name": str(row.get("stock_name") or ""),
            "market": str(row.get("market") or ""),
            "sector_name": sector,
            "industry": sector,
            "close": round_or_none(close, 2),
            "change": round_or_none(row.get("change"), 2),
            "change_pct": round_or_none(row.get("change_pct"), 2),
            "trade_value_yi": round_or_none(trade_value / 100_000_000, 2) if trade_value is not None else None,
            "foreign_net_shares": round_or_none(row.get("foreign_net_shares"), 0),
            "trustee_net_shares": round_or_none(row.get("trustee_net_shares"), 0),
            "dealer_net_shares": round_or_none(row.get("dealer_net_shares"), 0),
            "three_party_net_shares": round_or_none(net_shares, 0),
            "net_1d_yi": round_or_none(net_amount, 2),
            "stock_alpha_v4": round_or_none(score, 2),
            "alpha_score": round_or_none(score, 2),
            "sector_alpha_score": round_or_none(row.get("sector_alpha_score"), 2),
            "sector_alpha_component": round_or_none(row.get("sector_alpha_component"), 2),
            "main_buy_component": round_or_none(row.get("main_buy_component"), 2),
            "foreign_component": round_or_none(row.get("foreign_component"), 2),
            "trust_component": round_or_none(row.get("trust_component"), 2),
            "trade_value_component": round_or_none(row.get("trade_value_component"), 2),
            "momentum_component": round_or_none(row.get("momentum_component"), 2),
            "revenue_component": round_or_none(row.get("revenue_component"), 2),
            "quality_component": round_or_none(row.get("quality_component"), 2),
            "risk_penalty": round_or_none(row.get("risk_penalty"), 2),
            "risk_tags": risk_tags,
            "suggested_status": str(row.get("suggested_status") or "觀察"),
            "reason": build_stock_reason(row, score, sector, risk_tags),
            "source": source_name,
        }
        records.append(item)
    return records, data_date, source_name


def build_stock_reason(row: pd.Series, score: float, sector: str, risk_tags: list[str]) -> str:
    reasons = []
    net = to_float(row.get("three_party_net_shares"))
    if net is not None and net > 0:
        reasons.append("法人買超")
    if to_float(row.get("sector_alpha_score")) is not None:
        reasons.append(f"{sector} 類股分數支撐")
    if to_float(row.get("trade_value_component")) and to_float(row.get("trade_value_component")) > 0:
        reasons.append("成交值放大")
    if score >= 70:
        reasons.append("Alpha 高分")
    if risk_tags:
        reasons.append("需留意 " + "、".join(risk_tags[:2]))
    return " / ".join(reasons) if reasons else "列入觀察"


def make_stock_alpha_payload(records: list[dict[str, Any]], data_date: str | None, source_name: str) -> dict[str, Any]:
    return {
        "status": "ok" if records else "error",
        "version": "stock-alpha-v4-formal-v1",
        "data_timestamp": data_date,
        "as_of_date": data_date,
        "generated_at": now_iso(),
        "source": [source_name, "TWSE/TPEX official processed data", "FinMind supplemental data when available"],
        "calculation_location": "data_pipeline",
        "records": records,
        "items": records,
        "message": None if records else "資料尚未更新，請稍後再試",
    }


def make_sector_alpha_payload(records: list[dict[str, Any]], data_date: str | None) -> dict[str, Any]:
    ranked = sorted(records, key=lambda r: to_float(r.get("alpha_score")) or -1, reverse=True)
    for idx, row in enumerate(ranked, 1):
        row["alpha_rank"] = idx
    return {
        "status": "ok" if ranked else "error",
        "version": "sector-alpha-score-formal-v1",
        "data_timestamp": data_date,
        "as_of_date": data_date,
        "generated_at": now_iso(),
        "source": ["sector_rotation_latest.json"],
        "records": ranked,
        "items": ranked,
        "message": None if ranked else "資料尚未更新，請稍後再試",
    }


def make_recommendations_payload(stock_records: list[dict[str, Any]], data_date: str | None) -> dict[str, Any]:
    filtered = [r for r in stock_records if "避開" not in str(r.get("suggested_status") or "")]
    ranked = sorted(filtered, key=lambda r: to_float(r.get("stock_alpha_v4")) or -1, reverse=True)[:50]
    for idx, row in enumerate(ranked, 1):
        row["recommendation_rank"] = idx
    return {
        "status": "ok" if ranked else "error",
        "version": "recommendations-v4-formal-v1",
        "data_timestamp": data_date,
        "as_of_date": data_date,
        "generated_at": now_iso(),
        "source": ["stock_alpha_v4_latest.json"],
        "records": ranked,
        "items": ranked,
        "message": None if ranked else "資料尚未更新，請稍後再試",
    }


def make_backtest_payload(data_date: str | None) -> dict[str, Any]:
    candidates = ["backtest_alpha_v4.parquet", "backtest_alpha_v3.parquet", "recommendation_backtest.parquet", "factor_effectiveness.parquet"]
    summaries = []
    for name in candidates:
        df = read_parquet(name)
        if df.empty or "__read_error__" in df.columns:
            continue
        summary: dict[str, Any] = {
            "dataset": name,
            "rows": int(len(df)),
            "source_latest_date": latest_date(df) or data_date,
        }
        for col in ["annual_return", "annual_return_pct", "max_drawdown", "max_drawdown_pct", "win_rate", "sharpe", "total_return", "total_return_pct"]:
            if col in df.columns:
                summary[col] = round_or_none(pd.to_numeric(df[col], errors="coerce").dropna().tail(1).iloc[0] if not pd.to_numeric(df[col], errors="coerce").dropna().empty else None, 2)
        summaries.append(summary)
    return {
        "status": "ok" if summaries else "warning",
        "version": "backtest-v4-summary-formal-v1",
        "data_timestamp": data_date,
        "as_of_date": data_date,
        "generated_at": now_iso(),
        "source": candidates,
        "records": summaries,
        "summary": summaries[0] if summaries else {"message": "尚未找到 v4 回測 parquet；前端顯示資料狀態，不自行計算回測"},
    }


def make_chip_payload(stock_records: list[dict[str, Any]], data_date: str | None) -> dict[str, Any]:
    datasets = []
    for name in ["finmind_margin.parquet", "finmind_securities_lending.parquet", "finmind_shareholding.parquet", "finmind_composite_indicators.parquet"]:
        df = read_parquet(name)
        if not df.empty and "__read_error__" not in df.columns:
            datasets.append({"dataset": name, "rows": int(len(df)), "latest_date": latest_date(df, "date") or latest_date(df)})
    records = []
    for row in stock_records[:50]:
        records.append({
            "stock_id": row.get("stock_id"),
            "stock_name": row.get("stock_name"),
            "sector_name": row.get("sector_name"),
            "alpha_score": row.get("stock_alpha_v4"),
            "foreign_net_shares": row.get("foreign_net_shares"),
            "trustee_net_shares": row.get("trustee_net_shares"),
            "dealer_net_shares": row.get("dealer_net_shares"),
            "risk_tags": row.get("risk_tags") or [],
            "source": "stock_alpha_v4 chip proxy; FinMind chip datasets listed separately when available",
        })
    return {
        "status": "ok" if records else "warning",
        "version": "chip-analysis-formal-v1",
        "data_timestamp": data_date,
        "as_of_date": data_date,
        "generated_at": now_iso(),
        "source": ["FinMind chip datasets", "stock_alpha_v4_latest.json"],
        "available_finmind_datasets": datasets,
        "records": records,
        "items": records,
    }


def make_watchlist_payload(recommendations: list[dict[str, Any]], data_date: str | None) -> dict[str, Any]:
    records = recommendations[:20]
    return {
        "status": "ok" if records else "warning",
        "version": "watchlist-formal-v1",
        "data_timestamp": data_date,
        "as_of_date": data_date,
        "generated_at": now_iso(),
        "scope": "local_default_watchlist",
        "source": ["recommendations_v4_latest.json"],
        "records": records,
        "items": records,
    }


def json_clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return as_date(value)
    if hasattr(value, "item"):
        try:
            return json_clean(value.item())
        except Exception:
            pass
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    return value


def write_json(name: str, payload: dict[str, Any]) -> None:
    PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
    path = PUBLIC_DATA / name
    path.write_text(json.dumps(json_clean(payload), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def update_quality_report(generated: dict[str, dict[str, Any]]) -> None:
    report = read_json(QUALITY_PATH)
    if not isinstance(report, dict):
        report = {}
    report["formal_dashboard_json"] = {
        "status": "ok" if all(meta.get("status") in {"ok", "warning"} for meta in generated.values()) else "error",
        "generated_at": now_iso(),
        "files": generated,
    }
    QUALITY_PATH.write_text(json.dumps(json_clean(report), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    sector_flow = read_parquet("sector_flow.parquet")
    institutional_flow = read_parquet("institutional_flow.parquet")
    daily_price = read_parquet("daily_price.parquet")
    stock_alpha_breakdown = read_parquet("stock_alpha_breakdown.parquet")
    stock_alpha = read_parquet("stock_alpha.parquet")

    reference = read_json(PUBLIC_DATA / "sectorrotation_latest.json")
    reference_records = extract_reference_sectors(reference) if reference else []
    official_records, source_meta = build_official_sector_records(sector_flow, institutional_flow, daily_price, stock_alpha_breakdown, stock_alpha)

    records = reference_records or official_records
    data_date = first_present(reference, ["data_timestamp", "as_of_date", "date", "source_updated_at"]) if reference else None
    data_date = as_date(data_date) or latest_date(sector_flow) or latest_date(institutional_flow)
    records = enrich_sector_scores(records)

    stock_records, stock_date, stock_source = build_stock_alpha_records(stock_alpha_breakdown, stock_alpha)
    unified_date = data_date or stock_date

    payloads = {
        "sector_rotation_latest.json": sector_rotation_payload(reference, records, source_meta, unified_date),
        "cp_ranking_latest.json": make_cp_payload([dict(r) for r in records], unified_date),
        "bottom_fishing_latest.json": make_bottom_payload([dict(r) for r in records], unified_date),
        "sector_alpha_score.json": make_sector_alpha_payload([dict(r) for r in records], unified_date),
        "stock_alpha_v4_latest.json": make_stock_alpha_payload(stock_records, stock_date, stock_source),
    }
    recommendations_payload = make_recommendations_payload(stock_records, stock_date)
    payloads["recommendations_v4_latest.json"] = recommendations_payload
    payloads["backtest_v4_summary.json"] = make_backtest_payload(stock_date or unified_date)
    payloads["chip_analysis_latest.json"] = make_chip_payload(stock_records, stock_date)
    payloads["watchlist_latest.json"] = make_watchlist_payload(recommendations_payload.get("records", []), stock_date)

    generated_meta: dict[str, dict[str, Any]] = {}
    for filename, payload in payloads.items():
        write_json(filename, payload)
        generated_meta[filename] = {
            "status": payload.get("status"),
            "data_timestamp": payload.get("data_timestamp"),
            "records": len(payload.get("records") or payload.get("items") or []),
        }

    futures_path = PUBLIC_DATA / "futures_after_hours_latest.json"
    if futures_path.exists():
        futures = read_json(futures_path)
        generated_meta["futures_after_hours_latest.json"] = {
            "status": futures.get("status"),
            "data_timestamp": futures.get("data_timestamp") or futures.get("as_of_date") or futures.get("date"),
            "records": len(futures.get("records") or []),
        }

    update_quality_report(generated_meta)
    for filename, meta in generated_meta.items():
        print(f"{filename}: status={meta.get('status')} date={meta.get('data_timestamp')} records={meta.get('records')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
