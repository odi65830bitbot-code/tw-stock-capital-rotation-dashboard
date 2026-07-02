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
        stock_code = str(row.get("SecuritiesCompanyCode") or row.get("代號") or "").strip()
        # 去除不確定的空白 rank / 名稱
        if stock_code in ("", "0", "00000"):
            continue
        stock_name = str(row.get("CompanyName") or row.get("名稱") or "").strip()

        # 同時支援 Web API 英文 keys 與 CSV 中文 keys
        f_net = _parse_number(row.get("ForeignNetBuy") or row.get("外資及陸資(不含外資自營商)-買賣超股數") or row.get("外資及陸資-買賣超股數") or row.get("外資及陸資買賣超股數"))
        t_net = _parse_number(row.get("TrustNetBuy") or row.get("投信-買賣超股數") or row.get("投信買賣超股數"))
        d_net = _parse_number(row.get("DealerNetBuy") or row.get("自營商-買賣超股數") or row.get("自營商買賣超股數") or row.get("自營商合計買賣超股數"))
        net_buy = _parse_number(row.get("NetBuy") or row.get("三大法人買賣超股數合計") or row.get("三大法人買賣超股數"))

        f_buy = _parse_number(row.get("ForeignBuy") or row.get("外資及陸資-買進股數") or row.get("外資及陸資(不含外資自營商)-買進股數"))
        f_sell = _parse_number(row.get("ForeignSell") or row.get("外資及陸資-賣出股數") or row.get("外資及陸資(不含外資自營商)-賣出股數"))

        # 三大法人買賣超股數合計若為 None，則由外資、投信、自營商三者相加
        if net_buy is None and None not in (f_net, t_net, d_net):
            net_buy = f_net + t_net + d_net

        out.append(
            {
                "trade_date": _roc_to_ad(str(row.get("Date") or row.get("Date_Suffix") or row.get("Date") or "")),
                "market": "TPEX",
                "stock_code": stock_code,
                "stock_name": stock_name,
                "foreign_net_shares": f_net,
                "trustee_net_shares": t_net,
                "dealer_net_shares": d_net,
                "three_party_net_shares": net_buy,
                "foreign_buy_shares": f_buy,
                "foreign_sell_shares": f_sell,
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
        row_dict = {
            "trade_date": _roc_to_ad(str(row.get("Date", ""))),
            "market": "TPEX",
            "index_name": "TPEX_INDEX",
            "open": _parse_number(row.get("Open")),
            "high": _parse_number(row.get("High")),
            "low": _parse_number(row.get("Low")),
            "close": _parse_number(row.get("Close")),
            "change": _parse_number(row.get("Change")),
            "change_pct": None,
        }
        if row_dict["close"] is not None and row_dict["change"] is not None:
            prev_close = row_dict["close"] - row_dict["change"]
            if prev_close != 0:
                row_dict["change_pct"] = round((row_dict["change"] / prev_close) * 100, 2)
        out.append(row_dict)
    df = pd.DataFrame(out)
    if not df.empty:
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
    return df
