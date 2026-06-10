from __future__ import annotations

from typing import Any, Dict, Iterable, List

import pandas as pd


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace(",", "").replace("--", "").strip()
    if text in ("", "-"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _roc_to_ad(raw: str) -> str:
    if isinstance(raw, str) and len(raw) == 7 and raw[:3].isdigit():
        y = int(raw[:3]) + 1911
        return f"{y}{raw[3:5]}{raw[5:7]}"
    return raw


def normalize_tpex_daily_price(rows: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "trade_date": _roc_to_ad(str(row.get("Date", "") or row.get("資料日期", ""))),
                "market": "TPEX",
                "stock_code": str(row.get("SecuritiesCompanyCode", "") or row.get("代號", "")).strip(),
                "stock_name": str(row.get("CompanyName", "") or row.get("名稱", "")).strip(),
                "open": _parse_number(row.get("Open") or row.get("開盤")),
                "high": _parse_number(row.get("High") or row.get("最高")),
                "low": _parse_number(row.get("Low") or row.get("最低")),
                "close": _parse_number(row.get("Close") or row.get("收盤")),
                "change": _parse_number(row.get("Change") or row.get("漲跌")),
                "trade_volume": _parse_number(row.get("TradingShares") or row.get("成交股數")),
                "trade_value_twd": _parse_number(row.get("TransactionAmount") or row.get("成交金額")),
                "transactions": _parse_number(row.get("TransactionNumber") or row.get("成交筆數")),
            }
        )
    df = pd.DataFrame(out)
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
    return df


def normalize_tpex_institutional_flow(rows: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    out: List[Dict[str, Any]] = []
    for row in rows:
        stock_code = str(row.get("SecuritiesCompanyCode", "")).strip()
        # 去除不確定的空白 rank / 名稱
        if stock_code in ("", "0", "00000"):
            continue
        buy = _parse_number(row.get("Buy"))
        sell = _parse_number(row.get("Sell"))
        net_buy = _parse_number(row.get("NetBuy"))
        out.append(
            {
                "trade_date": _roc_to_ad(str(row.get("Date", ""))),
                "market": "TPEX",
                "stock_code": stock_code,
                "stock_name": str(row.get("CompanyName", "")).strip(),
                "three_party_net_shares": net_buy * 1000 if net_buy is not None else None,
                "foreign_buy_shares": buy * 1000 if buy is not None else None,
                "foreign_sell_shares": sell * 1000 if sell is not None else None,
                "rank": _parse_number(row.get("Rank")),
            }
        )
    df = pd.DataFrame(out)
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
    return df


def normalize_tpex_institutional_amount(rows: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "trade_date": _roc_to_ad(str(row.get("Date", ""))),
                "market": "TPEX",
                "investor": str(row.get("Investor", "")).strip() or "N/A",
                "purchase_amount_twd": _parse_number(row.get("PurchaseAmount")),
                "sale_amount_twd": _parse_number(row.get("SaleAmount")),
                "net_amount_twd": _parse_number(row.get("Net")),
            }
        )
    df = pd.DataFrame(out)
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
    return df


def normalize_tpex_sector_classification(rows: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "as_of_date": _roc_to_ad(str(row.get("Date", ""))),
                "stock_code": str(row.get("SecuritiesCompanyCode", "")).strip(),
                "stock_name": str(row.get("CompanyName", "")).strip(),
                "industry": str(row.get("SecuritiesIndustryCode", "")).strip(),
                "market": "TPEX",
            }
        )
    df = pd.DataFrame(out)
    df["as_of_date"] = pd.to_datetime(df["as_of_date"], format="%Y%m%d", errors="coerce")
    return df


def normalize_tpex_indices(rows: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    out: List[Dict[str, Any]] = []
    for row in rows:
        if "TPEx50Index" in row:
            out.append(
                {
                    "trade_date": _roc_to_ad(str(row.get("Date", ""))),
                    "market": "TPEX",
                    "index_name": "TPEx50Index",
                    "open": None,
                    "high": None,
                    "low": None,
                    "close": _parse_number(row.get("TPEx50Index")),
                    "change": None,
                    "change_pct": None,
                }
            )
            continue
        out.append(
            {
                "trade_date": _roc_to_ad(str(row.get("Date", ""))),
                "market": "TPEX",
                "index_name": "TPEX_INDEX",
                "open": _parse_number(row.get("Open")),
                "high": _parse_number(row.get("High")),
                "low": _parse_number(row.get("Low")),
                "close": _parse_number(row.get("Close")),
                "change": _parse_number(row.get("Change")),
            }
        )
    df = pd.DataFrame(out)
    if not df.empty:
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
    return df
