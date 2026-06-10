from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


def _df(payload: dict[str, Any], key: str) -> pd.DataFrame:
    df = pd.DataFrame(payload.get(key, []))
    if not df.empty and "trade_date" in df.columns:
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    return df


def _line_chart(payload: dict[str, Any], key: str, columns: list[str], title: str) -> None:
    st.markdown(f"#### {title}")
    df = _df(payload, key)
    cols = [col for col in columns if col in df.columns]
    if df.empty or not cols:
        st.info(f"尚無{title}資料")
        return
    st.line_chart(df.set_index("trade_date")[cols])


def render_finmind_trend_tabs(payload: dict[str, Any]) -> None:
    tabs = st.tabs(["價格趨勢", "法人資金", "融資融券", "月營收", "Alpha 變化", "推薦後績效", "風險"])
    with tabs[0]:
        _line_chart(payload, "price", ["close", "ma5", "ma20", "ma60"], "價格趨勢")
        _line_chart(payload, "trade_value", ["trade_value", "trade_value_ma20"], "成交值")
    with tabs[1]:
        _line_chart(
            payload,
            "institutional",
            ["foreign_buy_5d", "foreign_buy_20d", "investment_trust_buy_5d", "investment_trust_buy_20d"],
            "法人資金",
        )
    with tabs[2]:
        _line_chart(payload, "margin", ["margin_balance", "short_balance"], "融資融券")
    with tabs[3]:
        _line_chart(payload, "revenue", ["revenue_yoy", "revenue_mom"], "月營收")
    with tabs[4]:
        _line_chart(payload, "alpha", ["stock_alpha_v3", "sector_alpha", "main_force_proxy", "risk_penalty_total"], "Alpha 變化")
    with tabs[5]:
        rec = payload.get("recommendation", {})
        st.json({k: rec.get(k) for k in ["recommendation_type", "status", "backtest_win_rate", "backtest_avg_return_20d", "backtest_max_drawdown"]})
    with tabs[6]:
        rec = payload.get("recommendation", {})
        st.write(rec.get("main_risk_1") or "大盤與產業輪動變化")
        st.write(rec.get("main_risk_2") or "資料完整度與公告延遲")
