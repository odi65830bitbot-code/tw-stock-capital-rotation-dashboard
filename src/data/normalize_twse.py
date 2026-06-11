from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List

import pandas as pd


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace(",", "").replace("--", "").strip()
    text = (
        text.replace("<p style= color:red>+</p>", "")
        .replace("<p style= color:green>-</p>", "-")
        .replace("<p style ='color:red'>+</p>", "")
        .replace("<p style ='color:green'>-</p>", "-")
    )
    if text in ("", "-"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _roc_to_ad(raw: str) -> str:
    if not isinstance(raw, str):
        return raw
    # 115/06/10 -> 20260610
    if "/" in raw:
        parts = raw.split("/")
        if len(parts) == 3 and parts[0].isdigit():
            y = int(parts[0]) + 1911
            return f"{y}{parts[1].zfill(2)}{parts[2].zfill(2)}"
    # 1150607 -> 20260607
    if len(raw) == 7 and raw[:3].isdigit():
        y = int(raw[:3]) + 1911
        return f"{y}{raw[3:5]}{raw[5:7]}"
    return raw


def _signed_twse_change(sign: Any, value: Any) -> float | None:
    parsed = _parse_number(value)
    if parsed is None:
        return None
    sign_text = str(sign or "").lower()
    if "-" in sign_text or "green" in sign_text:
        return -abs(parsed)
    return parsed


def normalize_twse_daily_price(rows: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    out: List[Dict[str, Any]] = []
    for row in rows:
        raw_date = str(row.get("Date", "") or row.get("date", ""))
        stock_code = str(row.get("Code", "") or row.get("證券代號", "")).strip()
        stock_name = str(row.get("Name", "") or row.get("證券名稱", "")).strip()
        d = {
            "trade_date": _roc_to_ad(raw_date),
            "market": "TWSE",
            "stock_code": stock_code,
            "stock_name": stock_name,
            "open": _parse_number(row.get("OpeningPrice") or row.get("開盤價")),
            "high": _parse_number(row.get("HighestPrice") or row.get("最高價")),
            "low": _parse_number(row.get("LowestPrice") or row.get("最低價")),
            "close": _parse_number(row.get("ClosingPrice") or row.get("收盤價")),
            "change": (
                _parse_number(row.get("Change"))
                if row.get("Change") not in (None, "")
                else _signed_twse_change(row.get("漲跌(+/-)"), row.get("漲跌價差"))
            ),
            "trade_volume": _parse_number(row.get("TradeVolume") or row.get("成交股數")),
            "trade_value_twd": _parse_number(row.get("TradeValue") or row.get("成交金額")),
            "transactions": _parse_number(row.get("Transaction") or row.get("成交筆數")),
        }
        if stock_code:
            out.append(d)
    df = pd.DataFrame(out)
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
    return df


def normalize_twse_institutional_flow(rows: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    out: List[Dict[str, Any]] = []
    for row in rows:
        d = {
            "trade_date": _roc_to_ad(str(row.get("date", ""))),
            "market": "TWSE",
            "stock_code": str(row.get("證券代號", "")).strip(),
            "stock_name": str(row.get("證券名稱", "")).strip(),
            "foreign_net_shares": _parse_number(row.get("外陸資買賣超股數(不含外資自營商)")),
            "dealer_net_shares": _parse_number(row.get("自營商買賣超股數")),
            "trustee_net_shares": _parse_number(row.get("投信買賣超股數")),
            "three_party_net_shares": _parse_number(row.get("三大法人買賣超股數")),
            "foreign_net_shares_dealer": _parse_number(row.get("外資自營商買賣超股數")),
        }
        out.append(d)
    df = pd.DataFrame(out)
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
    return df


def normalize_twse_institutional_amount(rows: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "trade_date": _roc_to_ad(str(row.get("date", ""))),
                "market": "TWSE",
                "investor": str(row.get("單位名稱", "")).strip() or "N/A",
                "purchase_amount_twd": _parse_number(row.get("買進金額")),
                "sale_amount_twd": _parse_number(row.get("賣出金額")),
                "net_amount_twd": _parse_number(row.get("買賣差額")),
            }
        )
    df = pd.DataFrame(out)
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
    return df


def normalize_twse_sector_classification(rows: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "as_of_date": _roc_to_ad(str(row.get("出表日期", ""))),
                "stock_code": str(row.get("公司代號", "")).strip(),
                "stock_name": str(row.get("公司名稱", "")).strip(),
                "industry": str(row.get("產業別", "")).strip(),
                "market": "TWSE",
            }
        )
    df = pd.DataFrame(out)
    df["as_of_date"] = pd.to_datetime(df["as_of_date"], format="%Y%m%d", errors="coerce")
    return df


def normalize_twse_indices(rows: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    out: List[Dict[str, Any]] = []
    for row in rows:
        raw_date = _roc_to_ad(str(row.get("日期", "")) or str(row.get("Date", "")))
        if isinstance(row, dict) and "發行量加權股價指數" in row:
            row_dict = {
                "trade_date": raw_date,
                "market": "TWSE",
                "index_name": "TAIEX",
                "close": _parse_number(row.get("發行量加權股價指數")),
                "change": _parse_number(row.get("漲跌點數")),
                "change_pct": None,
                "open": None,
                "high": None,
                "low": None,
            }
            out.append(row_dict)
            continue
        if isinstance(row, dict) and "收盤指數" in row:
            row_dict = {
                "trade_date": raw_date,
                "market": "TWSE",
                "index_name": str(row.get("指數", "")).strip(),
                "close": _parse_number(row.get("收盤指數")),
                "change": _parse_number(row.get("漲跌點數")),
                "change_pct": _parse_number(str(row.get("漲跌百分比", "")).replace("%", "")),
                "open": None,
                "high": None,
                "low": None,
            }
            out.append(row_dict)
            continue
        out.append(
            {
                "trade_date": _roc_to_ad(str(row.get("Date", ""))),
                "market": "TWSE",
                "index_name": "TAIEX",
                "close": _parse_number(row.get("Close")),
                "change": _parse_number(row.get("Change")),
                "open": _parse_number(row.get("Open")),
                "high": _parse_number(row.get("High")),
                "low": _parse_number(row.get("Low")),
            }
        )
    df = pd.DataFrame(out)
    if not df.empty:
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
    return df
