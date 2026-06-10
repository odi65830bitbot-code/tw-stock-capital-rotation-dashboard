from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


def load_trend(stock_id: str, public_root: Path = Path("public")) -> dict[str, Any]:
    path = public_root / "data" / "trends" / f"{stock_id}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _df(payload: dict[str, Any], key: str) -> pd.DataFrame:
    rows = payload.get(key, []) if isinstance(payload, dict) else []
    df = pd.DataFrame(rows)
    if not df.empty and "trade_date" in df.columns:
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    return df


def render_price_trend(payload: dict[str, Any]) -> None:
    df = _df(payload, "price")
    st.markdown("#### 價格趨勢")
    if df.empty:
        st.info("尚無價格趨勢資料")
        return
    try:
        import plotly.graph_objects as go

        fig = go.Figure()
        for col, label in [("close", "收盤價"), ("ma5", "MA5"), ("ma20", "MA20"), ("ma60", "MA60")]:
            if col in df.columns:
                fig.add_trace(go.Scatter(x=df["trade_date"], y=df[col], mode="lines+markers", name=label))
        fig.update_layout(template="plotly_dark", height=320, margin=dict(l=12, r=12, t=12, b=12))
        st.plotly_chart(fig, width="stretch")
    except Exception:
        st.line_chart(df.set_index("trade_date")[[c for c in ["close", "ma5", "ma20", "ma60"] if c in df.columns]])


def render_volume_trend(payload: dict[str, Any]) -> None:
    df = _df(payload, "trade_value")
    st.markdown("#### 成交值趨勢")
    if df.empty:
        st.info("尚無成交值趨勢資料")
        return
    try:
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(go.Bar(x=df["trade_date"], y=df["trade_value_twd"], name="成交值"))
        if "trade_value_ma20" in df.columns:
            fig.add_trace(go.Scatter(x=df["trade_date"], y=df["trade_value_ma20"], mode="lines", name="20日均值"))
        fig.update_layout(template="plotly_dark", height=300, margin=dict(l=12, r=12, t=12, b=12))
        st.plotly_chart(fig, width="stretch")
    except Exception:
        st.bar_chart(df.set_index("trade_date")[[c for c in ["trade_value_twd"] if c in df.columns]])


def render_institutional_flow_trend(payload: dict[str, Any]) -> None:
    df = _df(payload, "institutional_flow")
    st.markdown("#### 法人資金趨勢")
    if df.empty:
        st.info("尚無法人資金趨勢資料")
        return
    try:
        import plotly.graph_objects as go

        fig = go.Figure()
        for col, label in [
            ("foreign_net_shares", "外資"),
            ("trustee_net_shares", "投信"),
            ("dealer_net_shares", "自營商"),
        ]:
            if col in df.columns:
                fig.add_trace(go.Bar(x=df["trade_date"], y=df[col], name=label))
        fig.update_layout(template="plotly_dark", barmode="relative", height=300, margin=dict(l=12, r=12, t=12, b=12))
        st.plotly_chart(fig, width="stretch")
    except Exception:
        cols = [c for c in ["foreign_net_shares", "trustee_net_shares", "dealer_net_shares"] if c in df.columns]
        st.bar_chart(df.set_index("trade_date")[cols])


def render_alpha_trend(payload: dict[str, Any]) -> None:
    df = _df(payload, "alpha")
    st.markdown("#### Alpha Score 趨勢")
    if df.empty:
        st.info("尚無 Alpha 趨勢資料")
        return
    cols = [c for c in ["alpha_score_total", "stock_alpha_score", "sector_alpha_score", "main_buy_component", "risk_penalty"] if c in df.columns]
    try:
        import plotly.graph_objects as go

        fig = go.Figure()
        for col in cols:
            fig.add_trace(go.Scatter(x=df["trade_date"], y=df[col], mode="lines+markers", name=col))
        fig.update_layout(template="plotly_dark", height=300, margin=dict(l=12, r=12, t=12, b=12))
        st.plotly_chart(fig, width="stretch")
    except Exception:
        st.line_chart(df.set_index("trade_date")[cols])


def render_recommendation_performance(payload: dict[str, Any]) -> None:
    rec = payload.get("recommendation", {}) if isinstance(payload, dict) else {}
    st.markdown("#### 推薦後績效")
    cols = st.columns(4)
    with cols[0]:
        st.metric("首次進入", rec.get("first_recommend_date") or "N/A")
    with cols[1]:
        value = rec.get("post_recommend_return")
        st.metric("推薦後報酬", "N/A" if value is None else f"{float(value):.2%}")
    with cols[2]:
        value = rec.get("post_recommend_max_drawdown")
        st.metric("最大回撤", "N/A" if value is None else f"{float(value):.2%}")
    with cols[3]:
        value = rec.get("post_recommend_max_gain")
        st.metric("最高漲幅", "N/A" if value is None else f"{float(value):.2%}")
