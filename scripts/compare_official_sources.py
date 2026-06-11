from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
PUBLIC_DATA = ROOT / "public" / "data"
REPORTS = ROOT / "reports"

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

FIELD_TOLERANCE = {
    "net_1d_yi": 0.05,
    "foreign_net_yi": 0.05,
    "trust_net_yi": 0.05,
    "dealer_net_yi": 0.05,
    "chg_1d": 0.05,
    "trade_value_yi": 0.05,
    "net_1d_shares": 1.0,
    "stock_count": 0.0,
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _date_text(value: Any) -> str | None:
    if value is None:
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return str(ts.date())


def _normalize_sector(value: Any) -> str:
    text = str(value or "").strip()
    return SECTOR_NAME_MAP.get(text, text)


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def _round(value: Any, digits: int = 2) -> float | None:
    num = _num(value)
    return round(num, digits) if num is not None else None


def _sector_key(row: dict[str, Any]) -> str:
    return f"{row.get('category') or row.get('market') or ''}|{row.get('sector_name') or row.get('industry') or row.get('name') or ''}"


def _with_change_pct(daily: pd.DataFrame) -> pd.DataFrame:
    out = daily.copy()
    if "change_pct" not in out.columns and {"close", "change"}.issubset(out.columns):
        close = pd.to_numeric(out["close"], errors="coerce")
        change = pd.to_numeric(out["change"], errors="coerce")
        prev = close - change
        out["change_pct"] = change / prev.where(prev != 0) * 100
    return out


def build_expected_sector_records(processed_root: Path = PROCESSED) -> dict[str, dict[str, Any]]:
    sector_flow = _read_parquet(processed_root / "sector_flow.parquet")
    institutional = _read_parquet(processed_root / "institutional_flow.parquet")
    daily = _with_change_pct(_read_parquet(processed_root / "daily_price.parquet"))
    classification = _read_parquet(processed_root / "sector_classification.parquet")
    if sector_flow.empty or institutional.empty or daily.empty:
        return {}

    latest_date = _date_text(sector_flow["trade_date"].max())
    if not latest_date:
        return {}

    sector_latest = sector_flow[sector_flow["trade_date"].map(_date_text) == latest_date].copy()
    inst_latest = institutional[institutional["trade_date"].map(_date_text) == latest_date].copy()
    price_latest = daily[daily["trade_date"].map(_date_text) == latest_date].copy()

    sector_map = {}
    if not classification.empty and {"stock_code", "industry"}.issubset(classification.columns):
        work = classification.copy()
        if "as_of_date" in work.columns:
            work = work.sort_values("as_of_date")
        sector_map = work.dropna(subset=["stock_code"]).drop_duplicates("stock_code", keep="last").set_index("stock_code")["industry"].to_dict()

    price_cols = [col for col in ["stock_code", "close", "change_pct", "trade_value_twd"] if col in price_latest.columns]
    inst = inst_latest.merge(price_latest[price_cols], on="stock_code", how="left")
    inst["industry"] = inst["stock_code"].map(sector_map).fillna("UNKNOWN")
    inst["sector_name"] = inst["industry"].map(_normalize_sector)
    if "market" not in inst.columns:
        inst["market"] = ""

    for col in ["three_party_net_shares", "foreign_net_shares", "trustee_net_shares", "dealer_net_shares", "close"]:
        if col in inst.columns:
            inst[col] = pd.to_numeric(inst[col], errors="coerce")

    inst["net_1d_yi_calc"] = inst["three_party_net_shares"] * inst["close"] / 100_000_000
    inst["foreign_net_yi_calc"] = inst["foreign_net_shares"] * inst["close"] / 100_000_000
    inst["trust_net_yi_calc"] = inst["trustee_net_shares"] * inst["close"] / 100_000_000
    inst["dealer_net_yi_calc"] = inst["dealer_net_shares"] * inst["close"] / 100_000_000

    grouped = inst.groupby(["market", "sector_name"], dropna=False).agg(
        net_1d_yi=("net_1d_yi_calc", "sum"),
        foreign_net_yi=("foreign_net_yi_calc", "sum"),
        trust_net_yi=("trust_net_yi_calc", "sum"),
        dealer_net_yi=("dealer_net_yi_calc", "sum"),
        chg_1d=("change_pct", "mean"),
        trade_value_yi=("trade_value_twd", lambda s: pd.to_numeric(s, errors="coerce").sum() / 100_000_000),
    ).reset_index()

    expected: dict[str, dict[str, Any]] = {}
    for _, row in grouped.iterrows():
        key = f"{row.get('market')}|{row.get('sector_name')}"
        expected[key] = {
            "category": row.get("market"),
            "sector_name": row.get("sector_name"),
            "net_1d_yi": _round(row.get("net_1d_yi"), 2),
            "foreign_net_yi": _round(row.get("foreign_net_yi"), 2),
            "trust_net_yi": _round(row.get("trust_net_yi"), 2),
            "dealer_net_yi": _round(row.get("dealer_net_yi"), 2),
            "chg_1d": _round(row.get("chg_1d"), 2),
            "trade_value_yi": _round(row.get("trade_value_yi"), 2),
        }

    for _, row in sector_latest.iterrows():
        sector_name = _normalize_sector(row.get("industry"))
        key = f"{row.get('market')}|{sector_name}"
        expected.setdefault(key, {"category": row.get("market"), "sector_name": sector_name})
        expected[key]["net_1d_shares"] = _round(row.get("three_party_net_shares"), 0)
        expected[key]["stock_count"] = int(_num(row.get("stock_count")) or 0)
    return expected


def compare_sector_rotation(public_data: Path = PUBLIC_DATA, processed_root: Path = PROCESSED) -> dict[str, Any]:
    payload = _read_json(public_data / "sector_rotation_latest.json")
    records = payload.get("records") or []
    expected = build_expected_sector_records(processed_root)
    rows = []
    mismatch_count = 0
    missing_expected = []

    for row in records:
        if not isinstance(row, dict):
            continue
        key = _sector_key(row)
        exp = expected.get(key)
        if not exp:
            missing_expected.append(key)
            continue
        fields = {}
        row_match = True
        for field, tolerance in FIELD_TOLERANCE.items():
            actual = _num(row.get(field))
            expected_value = _num(exp.get(field))
            if actual is None and expected_value is None:
                match = True
                diff = None
            elif actual is None or expected_value is None:
                match = False
                diff = None
            else:
                diff = round(actual - expected_value, 4)
                match = abs(diff) <= tolerance
            fields[field] = {
                "public": actual,
                "official_expected": expected_value,
                "diff": diff,
                "tolerance": tolerance,
                "match": match,
            }
            row_match = row_match and match
        if not row_match:
            mismatch_count += 1
        rows.append({"key": key, "match": row_match, "fields": fields})

    return {
        "status": "ok" if mismatch_count == 0 and not missing_expected else "mismatch",
        "public_file": "public/data/sector_rotation_latest.json",
        "official_sources": [
            "data/processed/sector_flow.parquet",
            "data/processed/institutional_flow.parquet",
            "data/processed/daily_price.parquet",
            "data/processed/sector_classification.parquet",
        ],
        "as_of_date": payload.get("as_of_date") or payload.get("data_timestamp"),
        "public_count": len(records),
        "expected_count": len(expected),
        "mismatch_count": mismatch_count,
        "missing_expected": missing_expected,
        "rows": rows,
    }


def compare_market(public_data: Path = PUBLIC_DATA, processed_root: Path = PROCESSED) -> dict[str, Any]:
    market_payload = _read_json(public_data / "market_latest.json")
    index_df = _read_parquet(processed_root / "index.parquet")
    records = market_payload.get("records") or []
    public_taiex = next((row for row in records if isinstance(row, dict) and row.get("index_name") == "TAIEX"), None)
    if public_taiex is None or index_df.empty:
        return {"status": "warning", "reason": "TAIEX public or official index data missing"}

    index_df = index_df[index_df["index_name"].astype(str).eq("TAIEX")].copy()
    if index_df.empty:
        return {"status": "warning", "reason": "official TAIEX row missing"}
    index_df = index_df.sort_values("trade_date")
    official = index_df.iloc[-1].to_dict()
    fields = {}
    for field in ["close", "change", "change_pct"]:
        actual = _num(public_taiex.get(field))
        expected = _num(official.get(field))
        if field == "change_pct" and expected is None:
            close = _num(official.get("close"))
            change = _num(official.get("change"))
            if close is not None and change is not None and close != change:
                expected = round(change / (close - change) * 100, 2)
        tolerance = 0.05
        match = actual is not None and expected is not None and abs(actual - expected) <= tolerance
        fields[field] = {"public": actual, "official_expected": expected, "diff": None if actual is None or expected is None else round(actual - expected, 4), "tolerance": tolerance, "match": match}
    status = "ok" if all(item["match"] for item in fields.values()) else "mismatch"
    return {"status": status, "fields": fields, "official_date": _date_text(official.get("trade_date"))}


def build_report(public_data: Path = PUBLIC_DATA, processed_root: Path = PROCESSED) -> dict[str, Any]:
    sector = compare_sector_rotation(public_data, processed_root)
    market = compare_market(public_data, processed_root)
    status = "ok" if sector["status"] == "ok" and market["status"] in {"ok", "warning"} else "mismatch"
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "method": "public dashboard JSON rechecked against official TWSE/TPEX processed data",
        "sector_rotation": sector,
        "market": market,
    }


def write_report(report: dict[str, Any], reports_root: Path = REPORTS) -> None:
    reports_root.mkdir(parents=True, exist_ok=True)
    (reports_root / "official_source_compare_latest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    sector = report["sector_rotation"]
    market = report["market"]
    lines = [
        "# 官方資料來源逐欄比對報告",
        "",
        f"- 產生時間：{report.get('generated_at')}",
        f"- 狀態：{report.get('status')}",
        f"- 方法：{report.get('method')}",
        f"- Dashboard 日期：{sector.get('as_of_date')}",
        f"- 產業筆數：public {sector.get('public_count')} / official expected {sector.get('expected_count')}",
        f"- 產業不一致數：{sector.get('mismatch_count')}",
        f"- 大盤比對狀態：{market.get('status')}",
    ]
    mismatches = [row for row in sector.get("rows", []) if not row.get("match")]
    if mismatches:
        lines.append("")
        lines.append("## 前 20 筆產業不一致")
        for row in mismatches[:20]:
            lines.append(f"- {row.get('key')}：{json.dumps(row.get('fields'), ensure_ascii=False)}")
    (reports_root / "official_source_compare_latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare dashboard JSON outputs against official TWSE/TPEX processed data.")
    parser.add_argument("--public-data", default=str(PUBLIC_DATA))
    parser.add_argument("--processed-root", default=str(PROCESSED))
    parser.add_argument("--reports-root", default=str(REPORTS))
    args = parser.parse_args()
    report = build_report(Path(args.public_data), Path(args.processed_root))
    write_report(report, Path(args.reports_root))
    print(json.dumps({
        "status": report["status"],
        "sector_mismatch_count": report["sector_rotation"]["mismatch_count"],
        "public_count": report["sector_rotation"]["public_count"],
        "expected_count": report["sector_rotation"]["expected_count"],
        "market_status": report["market"]["status"],
    }, ensure_ascii=False))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
