from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import streamlit as st

from src.modules.trend_charts import (
    load_trend,
    render_alpha_trend,
    render_institutional_flow_trend,
    render_price_trend,
    render_recommendation_performance,
    render_volume_trend,
)
from modules.trend_charts_finmind import render_finmind_trend_tabs
from src.stock_lookup import find_stock_matches
from src.data.trading_calendar import latest_complete_trade_date

CAT_META: dict[str, dict[str, Any]] = {
    "green": {
        "label": "主力",
        "sub": "資金加速流入",
        "color": "#2f7d5f",
    },
    "yellow": {
        "label": "輪動",
        "sub": "資金流入但放緩",
        "color": "#9b6b25",
    },
    "gray": {
        "label": "觀望",
        "sub": "資金沉寂",
        "color": "#7b867f",
    },
    "red": {
        "label": "退潮",
        "sub": "資金流出",
        "color": "#a64735",
    },
}


def _load_df(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_parquet(p)


def _load_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return pd.read_json(p)
    except Exception:
        import json

        with p.open("r", encoding="utf-8") as f:
            return json.load(f)


def _is_twse_code(code: Any) -> bool:
    if code is None:
        return False
    s = str(code).strip()
    return len(s) in (4, 5) and s.isdigit()


def _is_tpex_code(code: Any) -> bool:
    s = str(code).strip()
    return len(s) in (4, 5) and s.isdigit()


def _fmt_shares(v: float | int | None) -> str:
    if pd.isna(v):
        return "N/A"
    n = float(v)
    sign = "+" if n > 0 else ""
    abs_v = abs(n)
    if abs_v >= 1_000_000:
        return f"{sign}{n/1_000_000:,.2f}萬張"
    if abs_v >= 1000:
        return f"{sign}{n/1000:,.2f}張"
    return f"{sign}{n:,.0f}股"


def _fmt_number(v: float | int | None, precision: int = 2) -> str:
    if pd.isna(v):
        return "N/A"
    return f"{float(v):,.{precision}f}"


def _fmt_pct(v: float | int | None, precision: int = 2) -> str:
    if pd.isna(v):
        return "N/A"
    return f"{float(v) * 100:,.{precision}f}%"


def _format_date(v: Any) -> str:
    if pd.isna(v):
        return "N/A"
    if isinstance(v, str):
        return v
    try:
        return pd.to_datetime(v).strftime("%Y-%m-%d")
    except Exception:
        return str(v)


def _classify_sector(row: pd.Series) -> str:
    net5 = row.get("net_5d", 0.0)
    accel = row.get("accel", 0.0)
    if pd.isna(net5):
        return "gray"

    # 參考分群策略：主力/輪動/觀望/退潮
    if net5 > 0 and accel > 0:
        return "green"
    if net5 > 0 and accel <= 0:
        return "yellow"

    # 觀望區間：輕微負數，避免只看符號把所有小額都歸成退潮
    median_abs = abs(float(row.get("abs_flow_5d_median", 1.0)))
    if pd.isna(median_abs) or median_abs <= 0:
        median_abs = 1.0
    near_zero = 0.05 * median_abs
    if net5 >= -near_zero:
        return "gray"
    return "red"


def _safe_market_filter(df: pd.DataFrame, market: str) -> pd.DataFrame:
    if df.empty or market == "全部":
        return df
    return df[df["market"] == market].copy()


def _latest_date(*dfs: pd.DataFrame) -> pd.Timestamp | None:
    dates: list[pd.Timestamp] = []
    for df in dfs:
        if df is None or df.empty or "trade_date" not in df.columns:
            continue
        dates.append(pd.to_datetime(df["trade_date"]).max())
    if not dates:
        return None
    return max(dates)


def _display_trade_date(daily_df: pd.DataFrame, *fallback_dfs: pd.DataFrame) -> pd.Timestamp | None:
    complete = latest_complete_trade_date(daily_df)
    if complete is not None:
        return complete
    return _latest_date(daily_df, *fallback_dfs)


def _prepare_sector_view(
    sector_flow_df: pd.DataFrame,
    sector_alpha_df: pd.DataFrame,
    market: str,
    selected_market: str,
    keyword: str,
) -> pd.DataFrame:
    if sector_flow_df.empty:
        return pd.DataFrame()

    df = _safe_market_filter(sector_flow_df.copy(), selected_market)
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.dropna(subset=["industry", "three_party_net_shares", "trade_date"])
    df = df.sort_values(["market", "industry", "trade_date"])
    grouped = df.groupby(["market", "industry"], dropna=False)

    df["net_5d"] = grouped["three_party_net_shares"].transform(
        lambda s: s.rolling(5, min_periods=1).sum()
    )
    df["net_20d"] = grouped["three_party_net_shares"].transform(
        lambda s: s.rolling(20, min_periods=1).sum()
    )
    df["accel"] = (df["net_5d"] / 5.0) - (df["net_20d"] / 20.0)

    latest_date = df["trade_date"].max()
    latest = df[df["trade_date"] == latest_date].copy()
    if latest.empty:
        return pd.DataFrame()

    if not sector_alpha_df.empty:
        alpha = sector_alpha_df.copy()
        alpha["trade_date"] = pd.to_datetime(alpha["trade_date"])
        if selected_market != "全部":
            alpha = alpha[alpha["market"] == selected_market]
        latest = latest.merge(
            alpha[["trade_date", "market", "industry", "sector_alpha_score"]],
            on=["trade_date", "market", "industry"],
            how="left",
        )

    latest["abs_flow_5d_median"] = abs(df["net_5d"].median())
    latest["category"] = latest.apply(_classify_sector, axis=1)
    if "stock_count" not in latest.columns:
        latest["stock_count"] = 0

    if market != "全部":
        latest["market"] = market

    if keyword:
        key = keyword.lower().strip()
        latest = latest[
            latest["industry"].astype(str).str.lower().str.contains(key)
        ]

    latest = latest.sort_values(["market", "industry"])
    latest["cp_score"] = latest["sector_alpha_score"].fillna(0.0) * 1000 + latest["net_5d"].fillna(0.0)
    return latest.rename(columns={"market": "market"})


def _prepare_stock_view(
    daily_df: pd.DataFrame,
    stock_alpha_df: pd.DataFrame,
    selected_market: str,
    keyword: str,
    selected_sector: str,
) -> pd.DataFrame:
    if daily_df.empty and stock_alpha_df.empty:
        return pd.DataFrame()

    if daily_df.empty:
        df = stock_alpha_df.copy()
    else:
        daily = daily_df.copy()
        daily["trade_date"] = pd.to_datetime(daily["trade_date"], errors="coerce")
        latest_date = _display_trade_date(daily)
        daily = daily[daily["trade_date"] == latest_date].copy()

        if stock_alpha_df.empty:
            df = daily.copy()
            df["three_party_net_shares"] = pd.NA
            df["flow_abs"] = pd.NA
            df["flow_rate"] = pd.NA
            df["stock_alpha_score"] = 0.0
            df["industry"] = "UNKNOWN"
            df["has_institutional_flow"] = False
        else:
            alpha = stock_alpha_df.copy()
            alpha["trade_date"] = pd.to_datetime(alpha["trade_date"], errors="coerce")
            alpha = alpha[alpha["trade_date"] == latest_date].copy()
            keep_cols = [
                "trade_date",
                "market",
                "stock_code",
                "industry",
                "three_party_net_shares",
                "flow_abs",
                "flow_rate",
                "stock_alpha_score",
                "has_institutional_flow",
            ]
            alpha = alpha[[c for c in keep_cols if c in alpha.columns]]
            df = daily.merge(
                alpha,
                on=["trade_date", "market", "stock_code"],
                how="left",
            )
            df["industry"] = df.get("industry", pd.Series(index=df.index, dtype="object")).fillna("UNKNOWN")
            df["stock_alpha_score"] = df.get("stock_alpha_score", pd.Series(index=df.index, dtype="float64")).fillna(0.0)
            if "has_institutional_flow" not in df.columns:
                df["has_institutional_flow"] = df["three_party_net_shares"].notna() if "three_party_net_shares" in df.columns else False

    if df.empty:
        return df

    if selected_market != "全部":
        df = df[df["market"] == selected_market]
    if keyword:
        k = keyword.lower().strip()
        df = df[
            df["stock_code"].astype(str).str.contains(k)
            | df["stock_name"].astype(str).str.lower().str.contains(k)
            | df["industry"].astype(str).str.lower().str.contains(k)
        ]
        if not df.empty:
            code = df["stock_code"].astype(str).str.lower()
            name = df["stock_name"].astype(str).str.lower()
            industry = df["industry"].astype(str).str.lower()
            df["_match_rank"] = 9
            df.loc[code.eq(k), "_match_rank"] = 0
            df.loc[name.eq(k), "_match_rank"] = 1
            df.loc[code.str.startswith(k) & df["_match_rank"].eq(9), "_match_rank"] = 2
            df.loc[name.str.contains(k, na=False) & df["_match_rank"].eq(9), "_match_rank"] = 3
            df.loc[industry.str.contains(k, na=False) & df["_match_rank"].eq(9), "_match_rank"] = 4
    else:
        df["_match_rank"] = 9

    if selected_sector:
        df = df[df["industry"] == selected_sector]

    if df.empty:
        return df

    return (
        df.sort_values(["_match_rank", "stock_alpha_score", "trade_value_twd"], ascending=[True, False, False])
        .copy()
    )


def _format_stock_table(stock_df: pd.DataFrame, limit: int) -> pd.DataFrame:
    columns = [
        "trade_date",
        "market",
        "stock_code",
        "stock_name",
        "industry",
        "three_party_net_shares",
        "flow_abs",
        "flow_rate",
        "trade_volume",
        "trade_value_twd",
        "close",
        "stock_alpha_score",
        "revenue_component",
        "quality_component",
        "finmind_revenue_yoy_pct",
        "finmind_revenue_mom_pct",
        "finmind_per",
        "finmind_pbr",
        "has_institutional_flow",
    ]
    show = stock_df.head(limit).reindex(columns=columns).copy()
    show["trade_date"] = show["trade_date"].apply(_format_date)
    show["stock_code"] = show["stock_code"].astype(str)
    show["stock_alpha_score"] = show["stock_alpha_score"].apply(lambda x: _fmt_number(x, 4))
    show["three_party_net_shares"] = show["three_party_net_shares"].apply(_fmt_shares)
    show["flow_abs"] = show["flow_abs"].apply(_fmt_shares)
    show["flow_rate"] = show["flow_rate"].apply(lambda x: "N/A" if pd.isna(x) else _fmt_number(x * 100, 2) + "%")
    show["trade_volume"] = show["trade_volume"].apply(_fmt_shares)
    show["trade_value_twd"] = show["trade_value_twd"].apply(lambda x: _fmt_number(x, 0))
    show["revenue_component"] = show["revenue_component"].apply(lambda x: _fmt_number(x, 1))
    show["quality_component"] = show["quality_component"].apply(lambda x: _fmt_number(x, 1))
    show["finmind_revenue_yoy_pct"] = show["finmind_revenue_yoy_pct"].apply(lambda x: "N/A" if pd.isna(x) else _fmt_number(x, 2) + "%")
    show["finmind_revenue_mom_pct"] = show["finmind_revenue_mom_pct"].apply(lambda x: "N/A" if pd.isna(x) else _fmt_number(x, 2) + "%")
    show["finmind_per"] = show["finmind_per"].apply(lambda x: _fmt_number(x, 2))
    show["finmind_pbr"] = show["finmind_pbr"].apply(lambda x: _fmt_number(x, 2))
    show["has_institutional_flow"] = show["has_institutional_flow"].map(lambda x: "有" if bool(x) else "無")

    return show.rename(
        columns={
            "stock_code": "代號",
            "stock_name": "名稱",
            "market": "市場",
            "industry": "產業",
            "trade_date": "日期",
            "three_party_net_shares": "三方淨流入",
            "flow_abs": "流量絕對值",
            "flow_rate": "流向強度",
            "trade_volume": "成交量",
            "trade_value_twd": "成交值(元)",
            "close": "收盤價",
            "stock_alpha_score": "Alpha",
            "revenue_component": "營收分數",
            "quality_component": "估值品質",
            "finmind_revenue_yoy_pct": "營收YoY",
            "finmind_revenue_mom_pct": "營收MoM",
            "finmind_per": "PER",
            "finmind_pbr": "PBR",
            "has_institutional_flow": "法人資料",
        }
    )


def _render_stock_lookup(
    stock_view: pd.DataFrame,
    keyword: str,
    top_n: int,
    alpha_breakdown: pd.DataFrame | None = None,
) -> None:
    if not keyword.strip():
        return

    st.subheader("個股查詢結果")
    if stock_view.empty:
        st.warning(f"找不到「{keyword.strip()}」的個股資料")
        return

    first = stock_view.iloc[0]
    cols = st.columns(5)
    with cols[0]:
        st.metric("股票", f"{first.get('stock_code', 'N/A')} {first.get('stock_name', 'N/A')}", str(first.get("market", "N/A")))
    with cols[1]:
        st.metric("收盤價", _fmt_number(first.get("close"), 2))
    with cols[2]:
        st.metric("成交量", _fmt_shares(first.get("trade_volume")))
    with cols[3]:
        st.metric("三大法人", _fmt_shares(first.get("three_party_net_shares")))
    with cols[4]:
        st.metric("Alpha", _fmt_number(first.get("stock_alpha_score"), 4))

    st.dataframe(
        _format_stock_table(stock_view, min(max(top_n, 10), 50)),
        width="stretch",
        hide_index=True,
    )
    if alpha_breakdown is not None:
        _render_alpha_breakdown_panel(first, alpha_breakdown)


def _latest_market_status(index_df: pd.DataFrame) -> Dict[str, str]:
    if index_df.empty:
        return {}

    idx = index_df.copy()
    idx["trade_date"] = pd.to_datetime(idx["trade_date"])
    latest = idx["trade_date"].max()
    latest_idx = idx[idx["trade_date"] == latest]

    status: Dict[str, str] = {}
    for market, rows in latest_idx.groupby("market"):
        if rows.empty:
            continue
        key = market.upper()
        if rows.shape[0] == 0:
            continue

        # 取一個可讀名字（TWSE / TPEX）
        change_pct_cols = [c for c in rows.columns if c in ("change_pct", "change", "change_rate")]
        if "change_pct" in rows.columns and pd.notna(rows["change_pct"].max()):
            chg = float(rows["change_pct"].max())
        elif "change" in rows.columns and pd.notna(rows["change"].max()):
            close = float(rows["close"].max()) if "close" in rows.columns else 1.0
            chg = float(rows["change"].max()) / close * 100.0
        else:
            chg = 0.0
        status[key] = f"{chg:+.2f}%"
    return status


def _build_quality_summary(q: dict[str, Any]) -> pd.DataFrame:
    checks = q.get("checks", []) if isinstance(q, dict) else []
    if not checks:
        return pd.DataFrame(
            [{"項目": "品質報告", "結果": "無法讀取", "說明": "未找到品質報告"}]
        )

    rows = []
    for item in checks:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "項目": item.get("name", "-"),
                "結果": str(item.get("status", "")),
                "說明": str(item.get("message", "")),
            }
        )
    return pd.DataFrame(rows)


def _inject_style() -> None:
    st.markdown(
        """
        <style>
        :root {
            --app-bg: #eef3ed;
            --paper: #fbfcf7;
            --surface: rgba(251, 252, 247, 0.94);
            --surface-2: #e2eadf;
            --line: rgba(24, 37, 31, 0.16);
            --line-soft: rgba(24, 37, 31, 0.09);
            --text: #18251f;
            --muted: #66756c;
            --muted-2: #87948c;
            --accent: #2f6f5e;
            --accent-2: #2f6f5e;
            --good: #2f7d5f;
            --warn: #9b6b25;
            --bad: #a64735;
            --neutral: #7b867f;
            --radius: 16px;
            --mono: "SF Mono", ui-monospace, Menlo, Monaco, Consolas, monospace;
            --sans: "Avenir Next", "Noto Sans TC", "PingFang TC", -apple-system, BlinkMacSystemFont, sans-serif;
        }
        .block-container {
            max-width: 1320px;
            padding-top: 1.35rem;
            padding-bottom: 3rem;
        }
        .stApp {
            background:
                radial-gradient(circle at 12% 6%, rgba(47, 111, 94, 0.16), transparent 28rem),
                radial-gradient(circle at 88% 12%, rgba(47, 111, 94, 0.14), transparent 24rem),
                linear-gradient(180deg, rgba(251, 252, 247, 0.88), rgba(238, 243, 237, 0.98) 32rem),
                var(--app-bg);
            color: var(--text);
            font-family: var(--sans);
        }
        [data-testid="stSidebar"] {
            background: rgba(251, 252, 247, 0.95);
            border-right: 1px solid var(--line-soft);
            box-shadow: 18px 0 48px rgba(24, 37, 31, 0.06);
        }
        [data-testid="stSidebar"] * {
            color: var(--text);
        }
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] [data-baseweb="select"] {
            border-radius: var(--radius) !important;
        }
        h1, h2, h3, h4 {
            letter-spacing: -0.025em;
        }
        .stMarkdown p {
            line-height: 1.6;
        }
        .taste-shell {
            border: 1px solid var(--line-soft);
            border-radius: 28px;
            background:
                linear-gradient(135deg, rgba(251, 252, 247, 0.98), rgba(226, 234, 223, 0.9)),
                var(--paper);
            padding: 24px 26px;
            margin-bottom: 20px;
            box-shadow: 0 24px 70px rgba(24, 37, 31, 0.11);
            position: relative;
            overflow: hidden;
        }
        .taste-shell::after {
            content: "";
            position: absolute;
            inset: auto -8rem -10rem auto;
            width: 22rem;
            height: 22rem;
            border-radius: 999px;
            background: rgba(47, 111, 94, 0.1);
            pointer-events: none;
        }
        .taste-topline {
            display: flex;
            justify-content: space-between;
            gap: 16px;
            align-items: flex-start;
            flex-wrap: wrap;
        }
        .taste-title {
            font-size: clamp(2.55rem, 6vw, 4.9rem);
            line-height: 0.94;
            font-weight: 850;
            color: var(--text);
            margin: 0 0 10px;
            max-width: 9ch;
        }
        .taste-subtitle {
            max-width: 68ch;
            color: var(--muted);
            font-size: 1rem;
        }
        .taste-status-row {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
            margin-top: 18px;
        }
        .taste-pill {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            border: 1px solid var(--line);
            border-radius: var(--radius);
            padding: 8px 11px;
            color: var(--muted);
            background: rgba(255, 255, 255, 0.58);
            font-size: 0.82rem;
            font-weight: 700;
        }
        .taste-dot {
            width: 8px;
            height: 8px;
            border-radius: 999px;
            background: var(--accent);
            box-shadow: 0 0 0 4px rgba(47, 111, 94, 0.12);
        }
        .taste-kpi {
            border: 1px solid var(--line-soft);
            border-radius: var(--radius);
            padding: 12px 14px;
            background: rgba(255, 255, 255, 0.48);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
        }
        .taste-kpi-label,
        .metric-card .label,
        .direction-card .label,
        .rec-card .label {
            color: var(--muted);
            font-size: 0.74rem;
            margin-bottom: 4px;
        }
        .taste-kpi-value {
            color: var(--text);
            font-family: var(--mono);
            font-size: 1.1rem;
            font-weight: 800;
            letter-spacing: -0.02em;
        }
        .taste-data-note {
            margin-top: 12px;
            padding: 10px 12px;
            border-radius: var(--radius);
            border: 1px solid rgba(47, 111, 94, 0.18);
            background: rgba(47, 111, 94, 0.07);
            color: var(--muted);
            font-size: 0.84rem;
        }
        .taste-data-note strong {
            color: var(--text);
        }
        .taste-section-head {
            display: flex;
            justify-content: space-between;
            align-items: end;
            gap: 16px;
            margin: 22px 0 10px;
            border-top: 1px solid var(--line-soft);
            padding-top: 20px;
        }
        .taste-section-head h2 {
            margin: 0;
            color: var(--text);
            font-size: clamp(1.55rem, 3vw, 2.25rem);
            font-weight: 850;
        }
        .taste-section-head p {
            margin: 4px 0 0;
            color: var(--muted);
            font-size: 0.88rem;
        }
        .taste-action-row {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 10px;
        }
        .taste-action,
        .taste-action button {
            border: 1px solid rgba(47, 111, 94, 0.28);
            color: var(--accent-2);
            background: rgba(47, 111, 94, 0.08);
            border-radius: var(--radius);
            padding: 6px 10px;
            font-size: 0.76rem;
            font-weight: 700;
        }
        .taste-action:active {
            transform: translateY(1px);
        }
        .watchlist-bar {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            align-items: center;
            border: 1px solid rgba(47, 111, 94, 0.22);
            border-radius: var(--radius);
            padding: 10px 12px;
            margin: 4px 0 14px;
            background: rgba(47, 111, 94, 0.07);
            color: var(--muted);
            font-size: 0.82rem;
        }
        .watchlist-chip {
            display: inline-flex;
            border-radius: 999px;
            padding: 4px 9px;
            color: var(--text);
            background: rgba(255, 255, 255, 0.58);
            border: 1px solid var(--line-soft);
            font-family: var(--mono);
        }
        div[data-testid="stButton"] button {
            border-radius: var(--radius);
            border-color: rgba(47, 111, 94, 0.28);
            background: rgba(47, 111, 94, 0.08);
            color: var(--accent-2);
            font-weight: 750;
        }
        .metric-card {
            background: var(--surface);
            border: 1px solid var(--line-soft);
            border-left: 5px solid var(--accent);
            border-radius: var(--radius);
            padding: 13px 15px;
            box-shadow: 0 14px 36px rgba(24, 37, 31, 0.08);
        }
        .metric-card .value {
            font-size: 1.55rem;
            font-weight: 700;
            font-family: var(--mono);
        }
        .metric-card .sub {
            color: var(--muted-2);
            font-size: 0.77rem;
            margin-top: 2px;
        }
        .stTabs [data-baseweb="tab"] {
            white-space: nowrap;
            border-radius: var(--radius);
            color: var(--muted);
            font-weight: 750;
        }
        .stTabs [aria-selected="true"] {
            color: var(--accent-2) !important;
        }
        .sector-card {
            background: var(--surface);
            border: 1px solid var(--line-soft);
            border-radius: var(--radius);
            padding: 13px 15px;
            box-shadow: 0 12px 32px rgba(24, 37, 31, 0.07);
        }
        .sector-card + .sector-card { margin-top: 0.4rem; }
        .badge {
            display: inline-block;
            border-radius: 999px;
            padding: 2px 8px;
            font-size: 0.72rem;
            margin-right: 6px;
        }
        .direction-card, .rec-card {
            background: var(--surface);
            border: 1px solid var(--line-soft);
            border-radius: var(--radius);
            padding: 15px 16px;
            min-height: 116px;
            box-shadow: 0 14px 38px rgba(24, 37, 31, 0.08);
        }
        .direction-card .value {
            color: var(--text);
            font-size: 1.25rem;
            font-weight: 800;
            line-height: 1.2;
            font-family: var(--mono);
        }
        .rec-card {
            margin-bottom: 0.75rem;
            border-left: 4px solid var(--status-color);
            transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
        }
        .rec-card:hover {
            transform: translateY(-1px);
            border-color: rgba(47, 111, 94, 0.28);
            background: rgba(255, 255, 255, 0.74);
        }
        .rec-card .stock-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
        }
        .rec-card .stock-name {
            color: var(--text);
            font-size: 1.05rem;
            font-weight: 800;
            line-height: 1.25;
        }
        .rec-card .score {
            color: var(--accent-2);
            font-weight: 800;
            white-space: nowrap;
            font-family: var(--mono);
        }
        .rec-card .meta, .rec-card li {
            color: var(--muted);
            font-size: 0.82rem;
        }
        .risk-tag {
            display: inline-block;
            border-radius: 999px;
            padding: 2px 8px;
            margin: 4px 4px 0 0;
            font-size: 0.72rem;
            color: #7a2f21;
            background: rgba(182, 83, 60, 0.11);
            border: 1px solid rgba(182, 83, 60, 0.25);
        }
        .status-tag {
            display: inline-block;
            border-radius: 999px;
            padding: 2px 8px;
            font-size: 0.72rem;
            color: #06121a;
            background: var(--status-color);
            font-weight: 800;
        }
        .scorebar {
            width: 100%;
            height: 6px;
            border-radius: 999px;
            background: transparent;
            overflow: hidden;
            margin: 4px 0 10px;
            border-bottom: 1px solid rgba(148, 163, 184, 0.18);
        }
        .scorebar > span {
            display: block;
            height: 100%;
            width: var(--score-width);
            background: var(--score-color);
        }
        [data-testid="stDataFrame"] {
            border: 1px solid var(--line-soft);
            border-radius: var(--radius);
            overflow: hidden;
            box-shadow: 0 14px 34px rgba(24, 37, 31, 0.06);
        }
        [data-testid="stMetric"] {
            background: var(--surface);
            border: 1px solid var(--line-soft);
            border-radius: var(--radius);
            padding: 12px 14px;
            box-shadow: 0 12px 30px rgba(24, 37, 31, 0.06);
        }
        [data-testid="stSelectbox"] label,
        [data-testid="stTextInput"] label,
        [data-testid="stNumberInput"] label,
        [data-testid="stRadio"] label {
            color: var(--text) !important;
            font-weight: 760;
        }
        input, textarea, [data-baseweb="select"] > div {
            border-radius: var(--radius) !important;
            border-color: var(--line) !important;
            background: rgba(255, 255, 255, 0.74) !important;
        }
        div[data-testid="stAlert"] {
            border-radius: var(--radius);
            border: 1px solid var(--line-soft);
        }
        @media (prefers-reduced-motion: reduce) {
            .rec-card { transition: none; }
            .rec-card:hover { transform: none; }
        }
        @media (max-width: 720px) {
            div[data-testid="column"] {
                width: 100% !important;
                min-width: 100% !important;
                flex: 1 1 100% !important;
            }
            .block-container {
                padding-top: 0.4rem;
                padding-left: 1rem;
                padding-right: 1rem;
            }
            .taste-shell {
                padding: 16px;
                margin-bottom: 10px;
            }
            .taste-subtitle {
                display: none;
            }
            .taste-status-row {
                grid-template-columns: 1fr 1fr;
                gap: 8px;
            }
            .taste-title {
                font-size: 2.25rem;
                line-height: 1.02;
                max-width: 100%;
            }
            .taste-kpi {
                padding: 8px;
            }
            .taste-kpi-value {
                font-size: 0.95rem;
            }
            .taste-action-row {
                gap: 5px;
            }
            .taste-section-head h2 {
                font-size: 1.35rem;
            }
            .direction-card, .rec-card {
                min-height: auto;
                margin-bottom: 0.65rem;
            }
            .taste-data-note {
                font-size: 0.8rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _build_sector_cards(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("目前沒有可視覺化的板塊資料，可能尚未抓到完整分類或流入資料")
        return

    counts = Counter(df["category"])  # type: ignore[arg-type]

    cols = st.columns(4)
    for idx, (cat, meta) in enumerate(CAT_META.items()):
        with cols[idx]:
            st.markdown(
                f"""
                <div class="metric-card" style="--accent:{meta['color']}">
                  <div class="label" style="color:{meta['color']}">{meta['label']}</div>
                  <div class="value" style="color:{meta['color']}">{counts.get(cat, 0)}</div>
                  <div class="sub">{meta['sub']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_section_header(title: str, subtitle: str = "") -> None:
    sub_html = f"<p>{escape(subtitle)}</p>" if subtitle else ""
    st.markdown(
        f"""
        <div class="taste-section-head">
          <div>
            <h2>{escape(title)}</h2>
            {sub_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_app_header(
    payload: dict[str, Any],
    quality: dict[str, Any],
    selected_market: str,
    selected_stock_query: str,
) -> None:
    quality_status = str(quality.get("status", "unknown") if isinstance(quality, dict) else "unknown")
    expected_date = quality.get("expected_trade_date", "N/A") if isinstance(quality, dict) else "N/A"
    generated_at = quality.get("generated_at", "N/A") if isinstance(quality, dict) else "N/A"
    checks = quality.get("checks", []) if isinstance(quality, dict) else []
    alignment_messages = [
        str(item.get("message"))
        for item in checks
        if isinstance(item, dict) and item.get("name") == "market_date_alignment"
    ]
    alignment_note = alignment_messages[0] if alignment_messages else "TWSE / TPEX 日期一致性待確認"
    query_label = selected_stock_query if selected_stock_query else "未指定"
    status_label = {
        "ok": "品質正常",
        "pass": "品質正常",
        "warning": "品質有警告",
        "fail": "品質異常",
        "error": "品質異常",
    }.get(quality_status, "品質待確認")
    st.markdown(
        f"""
        <div class="taste-shell">
          <div class="taste-topline">
            <div>
              <div class="taste-pill"><span class="taste-dot"></span>TWSE / TPEX 官方資料優先</div>
              <h1 class="taste-title">台股資金日報</h1>
              <div class="taste-subtitle">盤後先看資料是否同日，再看資金方向、產業輪動、推薦觀察標的與個股 Alpha 拆解。</div>
            </div>
            <div class="taste-action-row">
              <span class="taste-pill">市場 {escape(selected_market)}</span>
              <span class="taste-pill">查詢 {escape(query_label)}</span>
              <span class="taste-pill">Trend Top 10</span>
            </div>
          </div>
          <div class="taste-status-row">
            <div class="taste-kpi">
              <div class="taste-kpi-label">最新交易日</div>
              <div class="taste-kpi-value">{escape(str(payload.get("trade_date", "N/A")))}</div>
            </div>
            <div class="taste-kpi">
              <div class="taste-kpi-label">預期更新日</div>
              <div class="taste-kpi-value">{escape(str(expected_date))}</div>
            </div>
            <div class="taste-kpi">
              <div class="taste-kpi-label">每日原始 / 分析</div>
              <div class="taste-kpi-value">{escape(str(payload.get("daily_rows", 0)))} / {escape(str(payload.get("stock_rows", 0)))}</div>
            </div>
            <div class="taste-kpi">
              <div class="taste-kpi-label">資料品質</div>
              <div class="taste-kpi-value">{escape(status_label)}</div>
            </div>
          </div>
          <div class="taste-data-note">
            <strong>資料狀態</strong>：{escape(alignment_note)}。品質報告產生日 {escape(str(generated_at))}，畫面以共同完整交易日為準。
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_watchlist() -> None:
    watchlist = st.session_state.get("watchlist", [])
    if not watchlist:
        return
    chips = "".join(f"<span class='watchlist-chip'>{escape(str(item))}</span>" for item in watchlist[-12:])
    st.markdown(
        f"""
        <div class="watchlist-bar">
          <strong>觀察清單</strong>
          {chips}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _status_color(status: Any) -> str:
    return {
        "觀察": "#2f7d5f",
        "分批觀察": "#5f8f78",
        "等待確認": "#7b867f",
        "過熱": "#9b6b25",
        "避開": "#a64735",
    }.get(str(status), "#7b867f")


def _filter_recommendations(
    recommendations: pd.DataFrame,
    selected_market: str,
    selected_sector: str = "",
) -> pd.DataFrame:
    if recommendations.empty:
        return pd.DataFrame()
    df = recommendations.copy()
    if selected_market != "全部" and "market" in df.columns:
        df = df[df["market"] == selected_market]
    if selected_sector and "industry" in df.columns:
        df = df[df["industry"] == selected_sector]
    elif selected_sector and "sector" in df.columns:
        df = df[df["sector"] == selected_sector]
    if "is_excluded" in df.columns:
        df = df[~df["is_excluded"].astype(bool)]
    if "alpha_score_total" not in df.columns and "stock_alpha_v3" in df.columns:
        df["alpha_score_total"] = pd.to_numeric(df["stock_alpha_v3"], errors="coerce")
    if "trade_value_twd" not in df.columns:
        df["trade_value_twd"] = 0
    if "stock_code" not in df.columns and "stock_id" in df.columns:
        df["stock_code"] = df["stock_id"].astype(str)
    if "industry" not in df.columns and "sector" in df.columns:
        df["industry"] = df["sector"]
    if "suggested_status" not in df.columns and "status" in df.columns:
        df["suggested_status"] = df["status"]
    return df.sort_values(["alpha_score_total", "trade_value_twd"], ascending=[False, False])


def _summary_row(summary: pd.DataFrame, summary_type: str) -> pd.Series | None:
    if summary.empty or "summary_type" not in summary.columns:
        return None
    rows = summary[summary["summary_type"] == summary_type]
    if rows.empty:
        return None
    return rows.iloc[0]


def _summary_from_current_view(sector_view: pd.DataFrame, recommendations: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    sector_pool = sector_view[sector_view["industry"].astype(str).ne("UNKNOWN")].copy() if not sector_view.empty else pd.DataFrame()
    if not sector_pool.empty:
        strongest = sector_pool.sort_values("cp_score", ascending=False).iloc[0]
        rotation = sector_pool.sort_values("accel", ascending=False).iloc[0]
        fading = sector_pool.sort_values("net_5d", ascending=True).iloc[0]
        rows.extend(
            [
                {
                    "summary_type": "strongest_sector",
                    "market": strongest.get("market"),
                    "industry": strongest.get("industry"),
                    "score": strongest.get("cp_score"),
                    "description": "Sector Alpha 與資金流綜合排序",
                },
                {
                    "summary_type": "new_rotation_sector",
                    "market": rotation.get("market"),
                    "industry": rotation.get("industry"),
                    "score": rotation.get("accel"),
                    "description": "資金加速度與相對強弱改善",
                },
                {
                    "summary_type": "fading_sector",
                    "market": fading.get("market"),
                    "industry": fading.get("industry"),
                    "score": fading.get("net_5d"),
                    "description": "資金訊號轉弱或流出較明顯",
                },
            ]
        )
    if not recommendations.empty:
        rows.append(
            {
                "summary_type": "candidate_count",
                "market": "ALL",
                "industry": "ALL",
                "score": int(len(recommendations)),
                "description": "候選清單標的數",
            }
        )
        score_col = "three_party_net_shares" if "three_party_net_shares" in recommendations.columns else "stock_alpha_v3"
        if score_col not in recommendations.columns:
            score_col = "alpha_score_total"
        market_flow = recommendations.groupby("market", dropna=False)[score_col].mean()
        description = "候選清單三大法人淨流入合計" if score_col == "three_party_net_shares" else "候選清單 Alpha v3 平均分數"
        for market, score in market_flow.items():
            rows.append(
                {
                    "summary_type": "market_direction",
                    "market": market,
                    "industry": "ALL",
                    "score": score,
                    "description": description,
                }
            )
    return pd.DataFrame(rows)


def _render_direction_cards(summary: pd.DataFrame, recommendations: pd.DataFrame, selected_market: str) -> None:
    _render_section_header("今日資金方向", "以推薦候選清單的三大法人淨流入與產業 Alpha 判斷盤後資金路徑。")
    filtered_recs = _filter_recommendations(recommendations, selected_market)
    strongest = _summary_row(summary, "strongest_sector")
    rotation = _summary_row(summary, "new_rotation_sector")
    fading = _summary_row(summary, "fading_sector")
    count = int(len(filtered_recs)) if not filtered_recs.empty else 0

    market_rows = summary[summary["summary_type"] == "market_direction"] if not summary.empty and "summary_type" in summary.columns else pd.DataFrame()
    if selected_market != "全部" and not market_rows.empty:
        market_rows = market_rows[market_rows["market"] == selected_market]
    direction_value = _fmt_shares(market_rows["score"].sum()) if not market_rows.empty else "N/A"

    cards = [
        ("今日資金方向", direction_value, "候選清單三大法人淨流入合計", "#2f6f5e"),
        (
            "最強產業",
            f"{strongest.get('market', 'N/A')} {strongest.get('industry', 'N/A')}" if strongest is not None else "N/A",
            "Sector Alpha 與資金流綜合排序",
            "#2f7d5f",
        ),
        (
            "新輪動產業",
            f"{rotation.get('market', 'N/A')} {rotation.get('industry', 'N/A')}" if rotation is not None else "N/A",
            "資金加速度與相對強弱改善",
            "#9b6b25",
        ),
        (
            "退潮觀察",
            f"{fading.get('market', 'N/A')} {fading.get('industry', 'N/A')}" if fading is not None else "N/A",
            f"候選標的 {count} 檔",
            "#a64735",
        ),
    ]
    cols = st.columns(4)
    for idx, (label, value, sub, color) in enumerate(cards):
        with cols[idx]:
            st.markdown(
                f"""
                <div class="direction-card" style="border-left:4px solid {color}">
                  <div class="label">{escape(label)}</div>
                  <div class="value">{escape(str(value))}</div>
                  <div class="sub">{escape(str(sub))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _score_bar(label: str, value: Any, color: str = "#2f6f5e") -> str:
    score = 0.0 if pd.isna(value) else max(0.0, min(100.0, float(value)))
    return f"""
    <div class="label">{escape(label)} <span style="float:right;color:var(--text)">{score:.1f}</span></div>
    <div class="scorebar" style="--score-width:{score:.1f}%; --score-color:{color};"><span></span></div>
    """


def _render_recommendation_card(row: pd.Series, *, compact: bool = False) -> None:
    status = str(row.get("suggested_status", "觀察"))
    color = _status_color(status)
    risk_source = row.get("risk_flags") or row.get("main_risk_1") or ""
    risk_flags = [x for x in str(risk_source).split("、") if x]
    risk_html = "".join(f"<span class='risk-tag'>{escape(flag)}</span>" for flag in risk_flags)
    if not risk_html:
        risk_html = "<span class='risk-tag'>一般風險</span>"

    reasons = [
        str(row.get("reason_1") or ""),
        str(row.get("reason_2") or ""),
        str(row.get("reason_3") or ""),
    ]
    reasons_html = "".join(f"<li>{escape(reason)}</li>" for reason in reasons if reason)
    drawdown = row.get("model_max_drawdown", row.get("backtest_max_drawdown"))
    win_rate = row.get("model_win_rate", row.get("backtest_win_rate"))
    backtest_text = "資料不足" if pd.isna(win_rate) else _fmt_pct(win_rate)
    drawdown_text = "資料不足" if pd.isna(drawdown) else _fmt_pct(drawdown)

    st.markdown(
        f"""
        <div class="rec-card" style="--status-color:{color}">
          <div class="stock-title">
            <div>
              <div class="stock-name">{escape(str(row.get('stock_code', row.get('stock_id', 'N/A'))))} {escape(str(row.get('stock_name', 'N/A')))}</div>
              <div class="meta">{escape(str(row.get('market', 'N/A')))} / {escape(str(row.get('industry', 'N/A')))}</div>
            </div>
            <div style="text-align:right">
              <div class="score">{_fmt_number(row.get('alpha_score_total', row.get('stock_alpha_v3')), 1)}</div>
              <span class="status-tag">{escape(status)}</span>
            </div>
          </div>
          <div class="meta" style="margin-top:8px;">{escape(str(row.get('summary') or row.get('summary_reason') or ''))}</div>
          <div style="margin-top:8px;">{risk_html}</div>
          <ul style="margin:8px 0 0 18px; padding:0;">{reasons_html}</ul>
          <div class="meta" style="margin-top:8px;">
            主力 {_fmt_number(row.get('main_buy_component', row.get('main_force_proxy')), 0)} ｜ 外資 {_fmt_number(row.get('foreign_component', row.get('foreign_score')), 0)} ｜
            投信 {_fmt_number(row.get('trust_component', row.get('trust_score')), 0)} ｜ 成交值 {_fmt_number(row.get('trade_value_component'), 0)} ｜
            動能 {_fmt_number(row.get('momentum_component', row.get('momentum_score')), 0)} ｜ 營收 {_fmt_number(row.get('revenue_component', row.get('revenue_score')), 0)} ｜
            財務 {_fmt_number(row.get('quality_component', row.get('quality_score')), 0)} ｜ 估值 {_fmt_number(row.get('valuation_score'), 0)} ｜
            融資健康 {_fmt_number(row.get('credit_health_score'), 0)} ｜ 信心 {_fmt_number(row.get('confidence_score'), 0)} ｜
            風險扣分 {_fmt_number(row.get('risk_penalty'), 0)}
          </div>
          <div class="meta">
            YoY {('N/A' if pd.isna(row.get('finmind_revenue_yoy_pct')) else _fmt_number(row.get('finmind_revenue_yoy_pct'), 2) + '%')} ｜
            MoM {('N/A' if pd.isna(row.get('finmind_revenue_mom_pct')) else _fmt_number(row.get('finmind_revenue_mom_pct'), 2) + '%')} ｜
            PER {_fmt_number(row.get('finmind_per'), 2)} ｜ PBR {_fmt_number(row.get('finmind_pbr'), 2)}
          </div>
          <div class="meta">回測勝率 {backtest_text} ｜ 最大回撤 {drawdown_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_recommendation_actions(row: pd.Series, idx: int, context: str) -> None:
    code = str(row.get("stock_code", row.get("stock_id", ""))).strip()
    name = str(row.get("stock_name", "")).strip()
    if not code:
        return

    cols = st.columns(4)
    if cols[0].button("查看趨勢", key=f"{context}_trend_{code}_{idx}"):
        st.session_state["selected_trend_stock"] = code
        st.session_state["focused_recommendation"] = code
    if cols[1].button("查詢個股", key=f"{context}_lookup_{code}_{idx}"):
        st.query_params["stock"] = code
        st.session_state["focused_recommendation"] = code
        st.rerun()
    if cols[2].button("查看風險", key=f"{context}_risk_{code}_{idx}"):
        st.session_state["focused_recommendation"] = code
        st.session_state["focused_recommendation_tab"] = "risk"
    if cols[3].button("加入觀察", key=f"{context}_watch_{code}_{idx}"):
        watchlist = list(st.session_state.get("watchlist", []))
        label = f"{code} {name}".strip()
        if label not in watchlist:
            watchlist.append(label)
        st.session_state["watchlist"] = watchlist[-20:]

    if st.session_state.get("focused_recommendation") == code:
        risk = str(row.get("main_risk") or row.get("main_risk_1") or row.get("risk_flags") or "一般市場波動風險")
        status = str(row.get("suggested_status") or "觀察")
        summary = str(row.get("summary") or row.get("summary_reason") or "資金訊號仍需搭配自身研究。")
        st.info(f"{code} {name}｜{status}｜{summary}｜主要風險：{risk}")


def _render_recommendation_cards(
    recommendations: pd.DataFrame,
    selected_market: str,
    *,
    limit: int = 10,
    top_overall_only: bool = True,
    context: str = "rec",
) -> None:
    recs = _filter_recommendations(recommendations, selected_market)
    if recs.empty:
        st.info("目前沒有符合條件的觀察標的")
        return
    if top_overall_only and "is_top_overall" in recs.columns:
        top = recs[recs["is_top_overall"].astype(bool)].copy()
        if not top.empty:
            recs = top
    recs = recs.head(limit)
    cols = st.columns(2)
    for idx, (_, row) in enumerate(recs.iterrows()):
        with cols[idx % 2]:
            _render_recommendation_card(row)
            _render_recommendation_actions(row, idx, context)


def _render_top10_trend_panel(recommendations: pd.DataFrame, selected_market: str) -> None:
    recs = _filter_recommendations(recommendations, selected_market)
    if "is_top_overall" in recs.columns:
        top = recs[recs["is_top_overall"].astype(bool)].copy()
        if not top.empty:
            recs = top
    if "overall_rank" not in recs.columns:
        recs["overall_rank"] = range(1, len(recs) + 1)
    if "alpha_score_total" not in recs.columns and "stock_alpha_v3" in recs.columns:
        recs["alpha_score_total"] = recs["stock_alpha_v3"]
    recs = recs.sort_values(["overall_rank", "alpha_score_total"], ascending=[True, False], na_position="last").head(10)
    if recs.empty:
        st.info("目前沒有可顯示趨勢的推薦股")
        return

    options = {
        f"{row.stock_code} {row.stock_name}｜{row.market}｜Alpha {_fmt_number(row.alpha_score_total, 1)}": str(row.stock_code)
        for row in recs.itertuples()
    }
    selected_code = str(st.session_state.get("selected_trend_stock", "") or "")
    option_labels = list(options.keys())
    default_index = 0
    for idx, option_label in enumerate(option_labels):
        if options[option_label] == selected_code:
            default_index = idx
            break
    label = st.selectbox("查看推薦股趨勢", option_labels, index=default_index, key="top10_trend_stock")
    stock_id = options[label]
    st.session_state["selected_trend_stock"] = stock_id
    payload = load_trend(stock_id)
    if not payload:
        st.warning(f"{stock_id} 尚未產生 trend JSON，請先執行每日更新。")
        return

    st.markdown(f"### {payload.get('stock_id', stock_id)} {payload.get('stock_name', '')} Trend")
    if "stock_alpha_v3" in str(payload.get("alpha", "")) or "recommendation_event_marker" in payload:
        render_finmind_trend_tabs(payload)
    else:
        render_recommendation_performance(payload)
        render_price_trend(payload)
        render_volume_trend(payload)
        render_institutional_flow_trend(payload)
        render_alpha_trend(payload)


def _render_alpha_breakdown_panel(stock_row: pd.Series, alpha_breakdown: pd.DataFrame) -> None:
    if alpha_breakdown.empty:
        return
    code = str(stock_row.get("stock_code", ""))
    market = str(stock_row.get("market", ""))
    rows = alpha_breakdown[
        (alpha_breakdown["stock_code"].astype(str) == code)
        & (alpha_breakdown["market"].astype(str) == market)
    ]
    if rows.empty:
        return

    row = rows.iloc[0]
    st.markdown("#### Alpha Score 拆解")
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.metric("Alpha Score", _fmt_number(row.get("alpha_score_total"), 1), str(row.get("suggested_status", "N/A")))
    with c2:
        st.metric("風險扣分", _fmt_number(row.get("risk_penalty"), 1))
    with c3:
        st.metric("主要風險", str(row.get("risk_flags") or "一般風險"))

    components = [
        ("產業 Alpha 20%", "sector_alpha_component", "#44d19d"),
        ("主力買超 20%", "main_buy_component", "#64d6ff"),
        ("外資買超 15%", "foreign_component", "#7dd3fc"),
        ("投信買超 15%", "trust_component", "#a78bfa"),
        ("成交值 10%", "trade_value_component", "#f6c453"),
        ("股價動能 10%", "momentum_component", "#fb7185"),
        ("營收成長 5%", "revenue_component", "#8ea2bd"),
        ("財務品質 5%", "quality_component", "#8ea2bd"),
    ]
    left, right = st.columns(2)
    for idx, (label, col, color) in enumerate(components):
        with (left if idx % 2 == 0 else right):
            st.markdown(_score_bar(label, row.get(col), color), unsafe_allow_html=True)

    note_parts = []
    if not bool(row.get("revenue_data_available", False)):
        note_parts.append("營收成長目前採中性分數，待官方公告日資料接入後才納入。")
    if not bool(row.get("financial_quality_data_available", False)):
        note_parts.append("財務品質目前採中性分數，待財報公告日資料接入後才納入。")
    if note_parts:
        st.caption(" ".join(note_parts))


def _format_backtest_table(backtest_df: pd.DataFrame) -> pd.DataFrame:
    if backtest_df.empty:
        return pd.DataFrame()
    show = backtest_df.copy()
    for col in ["cumulative_return", "win_rate", "max_drawdown", "sharpe_ratio", "benchmark_0050_return", "benchmark_taiex_return"]:
        if col not in show.columns:
            show[col] = pd.NA
    show["cumulative_return"] = show["cumulative_return"].apply(_fmt_pct)
    show["win_rate"] = show["win_rate"].apply(_fmt_pct)
    show["max_drawdown"] = show["max_drawdown"].apply(_fmt_pct)
    show["benchmark_0050_return"] = show["benchmark_0050_return"].apply(_fmt_pct)
    show["benchmark_taiex_return"] = show["benchmark_taiex_return"].apply(_fmt_pct)
    show["sharpe_ratio"] = show["sharpe_ratio"].apply(lambda x: _fmt_number(x, 2))
    return show.rename(
        columns={
            "model": "模型",
            "top_n": "Top N",
            "status": "狀態",
            "lookback_days": "回看天數",
            "trading_days": "交易筆數",
            "cumulative_return": "累積報酬",
            "win_rate": "勝率",
            "max_drawdown": "最大回撤",
            "sharpe_ratio": "Sharpe Ratio",
            "benchmark_0050_return": "0050",
            "benchmark_taiex_return": "加權指數",
        }
    )


def _render_backtest_panel(backtest_df: pd.DataFrame) -> None:
    st.subheader("推薦模型績效")
    if backtest_df.empty:
        st.info("尚未產生回測資料")
        return
    ok_rows = backtest_df[backtest_df["status"] == "ok"] if "status" in backtest_df.columns else pd.DataFrame()
    if ok_rows.empty:
        st.warning("目前只有單日資料，無法完成最近一年回測；回測框架已保留無未來資料的驗證流程。")
    else:
        cols = st.columns(4)
        best = ok_rows.sort_values("cumulative_return", ascending=False).iloc[0]
        with cols[0]:
            st.metric("最佳 Top N", int(best.get("top_n", 0)))
        with cols[1]:
            st.metric("累積報酬", _fmt_pct(best.get("cumulative_return")))
        with cols[2]:
            st.metric("勝率", _fmt_pct(best.get("win_rate")))
        with cols[3]:
            st.metric("最大回撤", _fmt_pct(best.get("max_drawdown")))
    st.dataframe(_format_backtest_table(backtest_df), width="stretch", hide_index=True)


def _render_bubble_section(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("資料不足，無法繪製泡泡圖。")
        return

    # 風險考量：數值落在極端時，縮放仍保留最小/最大視窗避免噪音
    plot_df = df.copy()
    plot_df = plot_df.replace([float("inf"), -float("inf")], pd.NA).dropna(subset=["net_5d", "net_20d", "accel"])
    if plot_df.empty:
        st.info("資料不足，無法繪製泡泡圖。")
        return
    plot_df["size"] = plot_df["net_20d"].abs().clip(lower=0).fillna(0.0)
    plot_df["size"] = (plot_df["size"] / (plot_df["size"].max() if plot_df["size"].max() else 1.0)).clip(lower=0.15) * 44 + 8
    plot_df["x_label"] = plot_df["net_5d"].round(0)
    plot_df["y_label"] = plot_df["accel"].round(2)
    plot_df["category_label"] = plot_df["category"].map({k: v["label"] for k, v in CAT_META.items()}).fillna("觀望")

    color_scale = {
        "green": "#1D9E75",
        "yellow": "#E4B125",
        "gray": "#6b7280",
        "red": "#D85A30",
    }
    try:
        import plotly.express as px

        fig = px.scatter(
            plot_df,
            x="net_5d",
            y="accel",
            size="size",
            color="category",
            hover_name="industry",
            color_discrete_map=color_scale,
            hover_data={
                "market": True,
                "cp_score": ":.2f",
                "net_5d": ":,.2f",
                "net_20d": ":,.2f",
                "accel": ":,.2f",
                "sector_alpha_score": ":,.4f",
                "stock_count": "d",
                "category": False,
                "category_label": True,
                "size": False,
            },
            template="plotly_dark",
        )
        fig.update_traces(marker=dict(line=dict(width=1, color="#1a2230")), selector=dict(mode="markers"))
        fig.update_layout(
            paper_bgcolor="#101722",
            plot_bgcolor="#101722",
            margin=dict(l=16, r=16, t=16, b=16),
            legend_title_text="象限",
            height=540,
        )
        fig.update_xaxes(gridcolor="#253046", zerolinecolor="#4a607d", title="近5日淨流入（單位：股數）")
        fig.update_yaxes(gridcolor="#253046", zerolinecolor="#4a607d", title="資金加速度（股數/日）")
        fig.update_yaxes(tickprefix="")
        fig.add_hline(y=0, line_dash="dot", line_color="#4a5f7d")
        fig.add_vline(x=0, line_dash="dot", line_color="#4a5f7d")

        st.plotly_chart(fig, width="stretch")
        return
    except Exception:
        pass

    width = 920
    height = 520
    pad_l, pad_r, pad_t, pad_b = 76, 28, 24, 58
    x_min, x_max = float(plot_df["net_5d"].min()), float(plot_df["net_5d"].max())
    y_min, y_max = float(plot_df["accel"].min()), float(plot_df["accel"].max())
    if x_min == x_max:
        x_min -= 1
        x_max += 1
    if y_min == y_max:
        y_min -= 1
        y_max += 1
    x_pad = (x_max - x_min) * 0.08
    y_pad = (y_max - y_min) * 0.08
    x_min -= x_pad
    x_max += x_pad
    y_min -= y_pad
    y_max += y_pad

    def sx(v: float) -> float:
        return pad_l + (v - x_min) / (x_max - x_min) * (width - pad_l - pad_r)

    def sy(v: float) -> float:
        return height - pad_b - (v - y_min) / (y_max - y_min) * (height - pad_t - pad_b)

    x_zero = sx(0) if x_min <= 0 <= x_max else pad_l
    y_zero = sy(0) if y_min <= 0 <= y_max else height - pad_b

    circles = []
    for _, row in plot_df.iterrows():
        radius = max(7.0, min(30.0, float(row["size"]) / 1.6))
        color = color_scale.get(str(row.get("category", "gray")), "#6b7280")
        cx = sx(float(row["net_5d"]))
        cy = sy(float(row["accel"]))
        title = (
            f"{row.get('market', '')} {row.get('industry', '')}\\n"
            f"5日流入: {_fmt_shares(row.get('net_5d'))}\\n"
            f"加速度: {_fmt_number(row.get('accel'), 2)}\\n"
            f"Alpha: {_fmt_number(row.get('sector_alpha_score'), 4)}"
        )
        circles.append(
            f"""
            <circle cx="{cx:.2f}" cy="{cy:.2f}" r="{radius:.2f}" fill="{color}" fill-opacity="0.78" stroke="#111827" stroke-width="1.2">
              <title>{escape(title)}</title>
            </circle>
            """
        )

    svg = f"""
    <div style="width:100%; overflow-x:auto;">
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="板塊資金象限" style="width:100%; min-width:720px; height:540px; background:#101722; border:1px solid #263244; border-radius:8px;">
        <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{height-pad_b}" stroke="#344258" stroke-width="1"/>
        <line x1="{pad_l}" y1="{height-pad_b}" x2="{width-pad_r}" y2="{height-pad_b}" stroke="#344258" stroke-width="1"/>
        <line x1="{x_zero:.2f}" y1="{pad_t}" x2="{x_zero:.2f}" y2="{height-pad_b}" stroke="#4a607d" stroke-width="1" stroke-dasharray="5 5"/>
        <line x1="{pad_l}" y1="{y_zero:.2f}" x2="{width-pad_r}" y2="{y_zero:.2f}" stroke="#4a607d" stroke-width="1" stroke-dasharray="5 5"/>
        {''.join(circles)}
        <text x="{width/2:.0f}" y="{height-18}" text-anchor="middle" fill="#9fb0c7" font-size="13">近5日淨流入（股）</text>
        <text x="18" y="{height/2:.0f}" transform="rotate(-90 18 {height/2:.0f})" text-anchor="middle" fill="#9fb0c7" font-size="13">資金加速度（股/日）</text>
      </svg>
    </div>
    """
    st.markdown(svg, unsafe_allow_html=True)


def _render_sectorrotation_reference(sectors: pd.DataFrame, stocks: pd.DataFrame) -> None:
    if sectors.empty:
        return

    ref = sectors.copy()
    for col in ["rank", "net_1d_yi", "net_5d_yi", "net_20d_yi", "position", "chg_1d", "chg_5d", "stock_count"]:
        if col in ref.columns:
            ref[col] = pd.to_numeric(ref[col], errors="coerce")

    st.caption("資料來源：sectorrotation.netlify.app/data/latest.json。排序使用 net_1d_yi / net_5d_yi / net_20d_yi，單位為億元。")
    try:
        import plotly.express as px

        plot_df = ref.dropna(subset=["net_5d_yi", "net_20d_yi", "position"]).copy()
        if not plot_df.empty:
            plot_df["bubble_size"] = plot_df["net_20d_yi"].abs().clip(lower=1)
            fig = px.scatter(
                plot_df,
                x="net_5d_yi",
                y="position",
                size="bubble_size",
                color="net_1d_yi",
                hover_name="sector_name",
                hover_data={
                    "rank": True,
                    "net_1d_yi": ":.2f",
                    "net_5d_yi": ":.2f",
                    "net_20d_yi": ":.2f",
                    "chg_1d": ":.2f",
                    "chg_5d": ":.2f",
                    "stock_count": True,
                    "bubble_size": False,
                },
                color_continuous_scale=["#D85A30", "#E4B125", "#1D9E75"],
                template="plotly_dark",
            )
            fig.update_layout(
                paper_bgcolor="#101722",
                plot_bgcolor="#101722",
                margin=dict(l=16, r=16, t=16, b=16),
                height=540,
                coloraxis_colorbar_title="1日買賣超(億)",
            )
            fig.update_xaxes(gridcolor="#253046", zerolinecolor="#4a607d", title="近5日買賣超（億元）")
            fig.update_yaxes(gridcolor="#253046", zerolinecolor="#4a607d", title="位置分數")
            fig.add_vline(x=0, line_dash="dot", line_color="#4a5f7d")
            st.plotly_chart(fig, width="stretch")
    except Exception:
        pass

    table = ref.sort_values("rank").head(30)
    st.dataframe(
        table[
            [c for c in ["rank", "sector_name", "net_1d_yi", "net_5d_yi", "net_20d_yi", "position", "chg_1d", "chg_5d", "stock_count"] if c in table.columns]
        ].rename(
            columns={
                "rank": "排名",
                "sector_name": "板塊",
                "net_1d_yi": "1日買賣超(億)",
                "net_5d_yi": "5日買賣超(億)",
                "net_20d_yi": "20日買賣超(億)",
                "position": "位置",
                "chg_1d": "1日漲跌幅",
                "chg_5d": "5日漲跌幅",
                "stock_count": "成分股數",
            }
        ),
        width="stretch",
        hide_index=True,
    )

    if stocks.empty or "sector_name" not in stocks.columns:
        return
    sector_names = ref.sort_values("rank")["sector_name"].dropna().astype(str).tolist()
    if not sector_names:
        return
    selected_ref_sector = st.selectbox("查看板塊成分股", sector_names, index=0, key="sectorrotation_detail_select")
    detail = stocks[stocks["sector_name"].astype(str) == selected_ref_sector].copy()
    for col in ["sector_rank", "chg_1d", "net_1d_yi"]:
        if col in detail.columns:
            detail[col] = pd.to_numeric(detail[col], errors="coerce")
    detail = detail.sort_values("net_1d_yi", ascending=False, na_position="last")
    st.dataframe(
        detail[[c for c in ["stock_code", "chg_1d", "net_1d_yi"] if c in detail.columns]].rename(
            columns={
                "stock_code": "台股代號",
                "chg_1d": "1日漲跌幅",
                "net_1d_yi": "1日買賣超(億)",
            }
        ),
        width="stretch",
        hide_index=True,
    )


def _render_sectorrotation_home_cards(sectors: pd.DataFrame, stocks: pd.DataFrame) -> None:
    if sectors.empty:
        return

    ref = sectors.copy()
    for col in ["rank", "net_1d_yi", "net_5d_yi", "net_20d_yi", "position", "chg_1d", "chg_5d", "stock_count"]:
        if col in ref.columns:
            ref[col] = pd.to_numeric(ref[col], errors="coerce")
    ref = ref.sort_values("rank", na_position="last")
    leader = ref.iloc[0]
    top_three = ref.head(3)

    hot_stocks = pd.DataFrame()
    if not stocks.empty and "sector_name" in stocks.columns:
        hot_stocks = stocks[stocks["sector_name"].astype(str) == str(leader.get("sector_name", ""))].copy()
        for col in ["chg_1d", "net_1d_yi"]:
            if col in hot_stocks.columns:
                hot_stocks[col] = pd.to_numeric(hot_stocks[col], errors="coerce")
        hot_stocks = hot_stocks.sort_values("net_1d_yi", ascending=False, na_position="last").head(6)

    leader_name = escape(str(leader.get("sector_name", "N/A")))
    net_1d = _fmt_number(leader.get("net_1d_yi"), 2)
    net_5d = _fmt_number(leader.get("net_5d_yi"), 2)
    net_20d = _fmt_number(leader.get("net_20d_yi"), 2)
    chg_1d = _fmt_number(leader.get("chg_1d"), 2)
    stock_count = int(leader.get("stock_count") or 0)

    ranking_items = []
    for _, row in top_three.iterrows():
        ranking_items.append(
            f"""
            <div class="sr-rank-row">
              <span class="sr-rank-no">#{int(row.get('rank') or 0)}</span>
              <span class="sr-rank-name">{escape(str(row.get('sector_name', 'N/A')))}</span>
              <span class="sr-rank-value">{_fmt_number(row.get('net_1d_yi'), 2)} 億</span>
            </div>
            """
        )

    stock_chips = []
    for _, row in hot_stocks.iterrows():
        stock_chips.append(
            f"""
            <div class="sr-stock-chip">
              <div class="sr-stock-code">{escape(str(row.get('stock_code', '')))}</div>
              <div class="sr-stock-meta">
                <span>{_fmt_number(row.get('net_1d_yi'), 2)} 億</span>
                <span>{_fmt_number(row.get('chg_1d'), 2)}%</span>
              </div>
            </div>
            """
        )

    st.markdown(
        f"""
        <style>
          .sr-home-shell {{
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(139, 184, 166, .22);
            border-radius: 28px;
            padding: clamp(22px, 4vw, 38px);
            margin: 8px 0 26px;
            background:
              radial-gradient(circle at 14% 0%, rgba(29, 158, 117, .24), transparent 34%),
              linear-gradient(135deg, rgba(9, 18, 26, .98), rgba(16, 23, 34, .96) 58%, rgba(27, 38, 48, .96));
            box-shadow: 0 28px 90px rgba(0, 0, 0, .32);
          }}
          .sr-home-shell:before {{
            content: "";
            position: absolute;
            inset: 0;
            background-image:
              linear-gradient(rgba(255,255,255,.045) 1px, transparent 1px),
              linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px);
            background-size: 34px 34px;
            mask-image: radial-gradient(circle at 22% 8%, black, transparent 72%);
            pointer-events: none;
          }}
          .sr-home-grid {{
            position: relative;
            display: grid;
            grid-template-columns: minmax(0, 1.15fr) minmax(280px, .85fr);
            gap: 24px;
            align-items: stretch;
          }}
          .sr-kicker {{
            color: #8fe6bd;
            font-size: 13px;
            letter-spacing: .14em;
            text-transform: uppercase;
            margin-bottom: 14px;
          }}
          .sr-title {{
            color: #f4f7f1;
            font-size: clamp(34px, 5.2vw, 70px);
            line-height: .94;
            letter-spacing: -.055em;
            margin: 0 0 18px;
            font-weight: 800;
          }}
          .sr-subtitle {{
            max-width: 640px;
            color: rgba(225, 235, 226, .76);
            font-size: 16px;
            line-height: 1.7;
            margin-bottom: 26px;
          }}
          .sr-metric-row {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
          }}
          .sr-metric {{
            border: 1px solid rgba(255,255,255,.10);
            border-radius: 18px;
            padding: 15px 16px;
            background: rgba(255, 255, 255, .055);
          }}
          .sr-metric-label {{
            color: rgba(225,235,226,.58);
            font-size: 12px;
            margin-bottom: 8px;
          }}
          .sr-metric-value {{
            color: #f7fff9;
            font-size: 22px;
            font-weight: 760;
            letter-spacing: -.03em;
          }}
          .sr-side-card {{
            border: 1px solid rgba(143, 230, 189, .22);
            border-radius: 24px;
            padding: 20px;
            background: linear-gradient(180deg, rgba(255,255,255,.095), rgba(255,255,255,.045));
            backdrop-filter: blur(18px);
          }}
          .sr-side-title {{
            color: #f4f7f1;
            font-size: 15px;
            font-weight: 760;
            margin-bottom: 12px;
          }}
          .sr-rank-row {{
            display: grid;
            grid-template-columns: 44px minmax(0, 1fr) auto;
            gap: 10px;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid rgba(255,255,255,.08);
          }}
          .sr-rank-row:last-child {{
            border-bottom: 0;
          }}
          .sr-rank-no {{
            color: #8fe6bd;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
          }}
          .sr-rank-name {{
            color: rgba(244,247,241,.92);
            font-weight: 700;
          }}
          .sr-rank-value {{
            color: #f4f7f1;
            font-weight: 760;
          }}
          .sr-stock-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
            margin-top: 16px;
          }}
          .sr-stock-chip {{
            border-radius: 16px;
            padding: 12px;
            background: rgba(10, 18, 24, .52);
            border: 1px solid rgba(255,255,255,.08);
          }}
          .sr-stock-code {{
            color: #f7fff9;
            font-weight: 800;
            margin-bottom: 8px;
          }}
          .sr-stock-meta {{
            display: flex;
            justify-content: space-between;
            gap: 8px;
            color: rgba(143,230,189,.9);
            font-size: 12px;
          }}
          @media (max-width: 900px) {{
            .sr-home-grid, .sr-metric-row {{
              grid-template-columns: 1fr;
            }}
            .sr-stock-grid {{
              grid-template-columns: repeat(2, minmax(0, 1fr));
            }}
          }}
        </style>
        <section class="sr-home-shell">
          <div class="sr-home-grid">
            <div>
              <div class="sr-kicker">SECTOR ROTATION LIVE</div>
              <h1 class="sr-title">{leader_name}<br>資金領跑</h1>
              <div class="sr-subtitle">
                首頁已改用你指定的板塊輪動資料，排序、泡泡圖與成分股明細都以對照站的億元買賣超為準。
              </div>
              <div class="sr-metric-row">
                <div class="sr-metric"><div class="sr-metric-label">1日買賣超</div><div class="sr-metric-value">{net_1d} 億</div></div>
                <div class="sr-metric"><div class="sr-metric-label">5日買賣超</div><div class="sr-metric-value">{net_5d} 億</div></div>
                <div class="sr-metric"><div class="sr-metric-label">20日買賣超</div><div class="sr-metric-value">{net_20d} 億</div></div>
                <div class="sr-metric"><div class="sr-metric-label">1日漲跌幅</div><div class="sr-metric-value">{chg_1d}%</div></div>
              </div>
            </div>
            <aside class="sr-side-card">
              <div class="sr-side-title">今日板塊排行</div>
              {''.join(ranking_items)}
              <div class="sr-side-title" style="margin-top:18px;">{leader_name} 成分股熱點，{stock_count} 檔</div>
              <div class="sr-stock-grid">{''.join(stock_chips)}</div>
            </aside>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def run_dashboard(
    daily_path: str = "data/processed/daily_price.parquet",
    stock_alpha_path: str = "data/processed/stock_alpha.parquet",
    stock_alpha_breakdown_path: str = "data/processed/stock_alpha_breakdown.parquet",
    recommendations_path: str = "data/processed/recommendations.parquet",
    recommendation_summary_path: str = "data/processed/recommendation_summary.parquet",
    sector_alpha_path: str = "data/processed/sector_alpha.parquet",
    sector_flow_path: str = "data/processed/sector_flow.parquet",
    index_path: str = "data/processed/index.parquet",
    quality_path: str = "data_quality_report.json",
    selected_market: str = "全部",
    keyword: str = "",
    selected_sector: str = "",
) -> dict[str, Any]:
    daily_df = _load_df(daily_path)
    stock_alpha = _load_df(stock_alpha_path)
    stock_alpha_breakdown = _load_df(stock_alpha_breakdown_path)
    recommendations = _load_df(recommendations_path)
    recommendation_summary = _load_df(recommendation_summary_path)
    sector_alpha = _load_df(sector_alpha_path)
    sector_flow = _load_df(sector_flow_path)
    index_df = _load_df(index_path)
    quality = _load_json(quality_path)

    if stock_alpha.empty and sector_flow.empty:
        return {
            "status": "empty",
            "trade_date": None,
            "stock_alpha": [],
            "sector_view": [],
            "market_status": {},
            "quality": quality,
        }

    latest = _display_trade_date(daily_df, stock_alpha, sector_alpha, sector_flow)
    sector_latest = latest_complete_trade_date(sector_flow) if not sector_flow.empty else None
    if sector_latest is None:
        sector_latest = _latest_date(sector_flow)
    daily_rows_for_display = int(len(daily_df))
    stock_rows_for_display = int(len(stock_alpha))
    if latest is not None:
        if not daily_df.empty and "trade_date" in daily_df.columns:
            daily_rows_for_display = int((pd.to_datetime(daily_df["trade_date"], errors="coerce") == latest).sum())
        if not stock_alpha.empty and "trade_date" in stock_alpha.columns:
            stock_rows_for_display = int((pd.to_datetime(stock_alpha["trade_date"], errors="coerce") == latest).sum())
        if not recommendations.empty and "trade_date" in recommendations.columns:
            recommendations = recommendations[pd.to_datetime(recommendations["trade_date"], errors="coerce") == latest].copy()
        if not index_df.empty and "trade_date" in index_df.columns:
            index_df = index_df[pd.to_datetime(index_df["trade_date"], errors="coerce") == latest].copy()
    if sector_latest is not None:
        if not sector_flow.empty and "trade_date" in sector_flow.columns:
            sector_flow = sector_flow[pd.to_datetime(sector_flow["trade_date"], errors="coerce") <= sector_latest].copy()
        if not sector_alpha.empty and "trade_date" in sector_alpha.columns:
            sector_alpha = sector_alpha[pd.to_datetime(sector_alpha["trade_date"], errors="coerce") <= sector_latest].copy()

    sector_view = _prepare_sector_view(sector_flow, sector_alpha, selected_market, selected_market, keyword)
    stock_view = _prepare_stock_view(daily_df, stock_alpha, selected_market, keyword, selected_sector)
    market_status = _latest_market_status(index_df)

    top_stocks = (
        stock_view.head(20)
        .reindex(
            columns=[
                "trade_date",
                "market",
                "stock_code",
                "stock_name",
                "industry",
                "three_party_net_shares",
                "trade_volume",
                "trade_value_twd",
                "close",
                "flow_abs",
                "flow_rate",
                "stock_alpha_score",
                "has_institutional_flow",
            ]
        )
        .to_dict(orient="records")
        if not stock_view.empty
        else []
    )
    top_recommendations = (
        _filter_recommendations(recommendations, selected_market)
        .head(10)
        .to_dict(orient="records")
        if not recommendations.empty
        else []
    )

    top_sectors = (
        sector_view[["market", "industry", "net_5d", "net_20d", "accel", "sector_alpha_score", "category", "cp_score"]]
        .sort_values("cp_score", ascending=False)
        .head(20)
        .to_dict(orient="records")
        if not sector_view.empty
        else []
    )

    return {
        "status": "ok",
        "trade_date": _format_date(latest),
        "sector_trade_date": _format_date(sector_latest),
        "daily_rows": daily_rows_for_display,
        "stock_rows": stock_rows_for_display,
        "sector_rows": int(len(sector_flow)),
        "stock_alpha": top_stocks,
        "stock_alpha_breakdown_rows": int(len(stock_alpha_breakdown)),
        "recommendations": top_recommendations,
        "recommendation_summary": recommendation_summary.to_dict(orient="records") if not recommendation_summary.empty else [],
        "sector_view": top_sectors,
        "market_status": market_status,
        "quality": quality,
    }


def run_streamlit_app() -> None:
    st.set_page_config(
        page_title="台股資金儀表板",
        layout="wide",
    )
    _inject_style()

    stock_param = str(st.query_params.get("stock", "") or "").strip()

    with st.sidebar:
        st.markdown("### 控制欄")
        selected_market = st.radio(
            "市場",
            options=["全部", "TWSE", "TPEX"],
            index=0,
            horizontal=True,
        )

        keyword = st.text_input(
            "搜尋（股票代號 / 股票名 / 產業）",
            value=stock_param,
            placeholder="例：2330 或 台積電",
        )
        if keyword.strip():
            st.query_params["stock"] = keyword.strip()
        elif stock_param:
            try:
                del st.query_params["stock"]
            except Exception:
                pass

        selected_cats = st.multiselect(
            "板塊象限",
            options=list(CAT_META.keys()),
            format_func=lambda x: CAT_META[x]["label"],
            default=list(CAT_META.keys()),
        )

        top_n = st.slider("Top N", min_value=10, max_value=200, step=10, value=30)
        alpha_mode = st.radio(
            "Alpha 模式",
            options=["Alpha v1：官方資料版", "Alpha v2：加入部分 FinMind", "Alpha v3：完整 FinMind 多因子版"],
            index=0,
        )

    payload = run_dashboard(selected_market=selected_market, keyword="")
    if payload["status"] != "ok":
        st.error("暫無可用資料，請先執行資料建置。")
        return

    quality = payload.get("quality", {}) if isinstance(payload.get("quality", {}), dict) else {}
    _render_app_header(payload, quality, selected_market, keyword.strip())

    if not selected_cats:
        selected_cats = list(CAT_META.keys())

    # 載入完整 sector_flow / stock_alpha 再做互動
    daily_df = _load_df("data/processed/daily_price.parquet")
    sector_flow = _load_df("data/processed/sector_flow.parquet")
    sector_alpha = _load_df("data/processed/sector_alpha.parquet")
    stock_alpha = _load_df("data/processed/stock_alpha.parquet")
    stock_alpha_breakdown = _load_df("data/processed/stock_alpha_breakdown.parquet")
    recommendations = _load_df("data/processed/recommendations.parquet")
    recommendation_summary = _load_df("data/processed/recommendation_summary.parquet")
    recommendation_backtest = _load_df("data/processed/recommendation_backtest.parquet")
    recommendations_v3 = _load_df("data/processed/recommendations_v3.parquet")
    stock_alpha_v3 = _load_df("data/processed/stock_alpha_v3.parquet")
    backtest_alpha_v3 = _load_df("data/processed/backtest_alpha_v3.parquet")
    factor_effectiveness = _load_df("data/processed/factor_effectiveness.parquet")
    sectorrotation_sector = _load_df("data/processed/sectorrotation_sector.parquet")
    sectorrotation_stock = _load_df("data/processed/sectorrotation_stock.parquet")
    sector_df = _load_df("data/processed/sector_classification.parquet")
    index_df = _load_df("data/processed/index.parquet")
    if alpha_mode.startswith("Alpha v3"):
        if not recommendations_v3.empty:
            recommendations = recommendations_v3
        if not stock_alpha_v3.empty:
            stock_alpha_breakdown = stock_alpha_v3
        if not backtest_alpha_v3.empty:
            recommendation_backtest = backtest_alpha_v3
        else:
            st.sidebar.warning("尚未產生 Alpha v3 回測，已保留官方資料版回測。")
    elif alpha_mode.startswith("Alpha v2"):
        st.sidebar.info("Alpha v2 使用現有官方資料加 FinMind composite 補強欄位。")
    display_date = _display_trade_date(daily_df, stock_alpha, sector_alpha, sector_flow)
    sector_display_date = latest_complete_trade_date(sector_flow) if not sector_flow.empty else None
    if sector_display_date is None:
        sector_display_date = _latest_date(sector_flow)
    if display_date is not None:
        if not recommendations.empty and "trade_date" in recommendations.columns:
            recommendations = recommendations[pd.to_datetime(recommendations["trade_date"], errors="coerce") == display_date].copy()
        if not index_df.empty and "trade_date" in index_df.columns:
            index_df = index_df[pd.to_datetime(index_df["trade_date"], errors="coerce") == display_date].copy()
    if sector_display_date is not None:
        if not sector_flow.empty and "trade_date" in sector_flow.columns:
            sector_flow = sector_flow[pd.to_datetime(sector_flow["trade_date"], errors="coerce") <= sector_display_date].copy()
        if not sector_alpha.empty and "trade_date" in sector_alpha.columns:
            sector_alpha = sector_alpha[pd.to_datetime(sector_alpha["trade_date"], errors="coerce") <= sector_display_date].copy()

    selected_stock_query = keyword.strip()
    lookup_matches = find_stock_matches(selected_stock_query, daily_df, sector_df, stock_alpha_breakdown) if selected_stock_query else []
    if selected_stock_query and lookup_matches:
        labels = [
            f"{item.stock_id} {item.stock_name}｜{item.market}｜{item.sector}"
            for item in lookup_matches
        ]
        default_idx = 0
        selected_label = st.selectbox("個股查詢結果", labels, index=default_idx, key="stock_lookup_select")
        selected_stock_query = lookup_matches[labels.index(selected_label)].stock_id
        st.query_params["stock"] = selected_stock_query
    elif selected_stock_query:
        st.warning(f"找不到此股票代號或名稱：{selected_stock_query}。若今日資料尚未更新，請先執行每日更新。")

    sector_keyword = "" if selected_stock_query else keyword
    sector_view = _prepare_sector_view(sector_flow, sector_alpha, selected_market, selected_market, sector_keyword)
    stock_view = _prepare_stock_view(daily_df, stock_alpha, selected_market, selected_stock_query, "")

    if not sector_view.empty:
        sector_view = sector_view[sector_view["category"].isin(selected_cats)]

    current_summary = _summary_from_current_view(sector_view, recommendations)

    _render_sectorrotation_home_cards(sectorrotation_sector, sectorrotation_stock)

    _render_section_header("推薦觀察標的 Top 10", "僅呈現資金訊號、Alpha 拆解與風險標籤，需搭配自身研究與風險控管。")
    _render_recommendation_cards(recommendations, selected_market, limit=10, context="home")
    _render_watchlist()
    _render_direction_cards(current_summary, recommendations, selected_market)

    with st.expander("品質報告", expanded=False):
        if quality:
            st.caption(f"生成時間：{quality.get('generated_at', 'N/A')}")
            st.json({k: quality.get(k) for k in ["status", "generated_at", "expected_trade_date"]})
            qdf = _build_quality_summary(quality)
            st.dataframe(qdf, width="stretch", hide_index=True)
        else:
            st.warning("無法載入品質報告")

    raw = quality.get("raw_sources", {}) if isinstance(quality, dict) else {}
    with st.expander("原始資料來源", expanded=False):
        if raw:
            st.json(raw)
        else:
            st.write("無原始來源資訊")

    # 左上角指標：市場狀態與象限
    col_left, col_mid, col_right = st.columns([1, 1, 2])

    with col_left:
        st.subheader("市場狀態")
        if index_df.empty:
            st.warning("缺少指數資料")
        else:
            st.markdown("<div class='sector-card'>", unsafe_allow_html=True)
            market_status = _latest_market_status(index_df)
            if not market_status:
                st.write("尚無可顯示行情")
            for m, chg in market_status.items():
                st.write(f"**{m}**\n{chg}")
            st.markdown("</div>", unsafe_allow_html=True)

    with col_mid:
        st.subheader("資料品質")
        quality_status = quality.get("status", "unknown") if isinstance(quality, dict) else "unknown"
        if quality_status in {"ok", "pass"}:
            st.success("品質：正常")
        elif quality_status == "warning":
            st.warning("品質：有警告，請查閱品質報告")
        else:
            st.error("品質：異常或未檢查")

    with col_right:
        st.subheader("最新回測預覽")
        if recommendation_backtest.empty:
            st.warning("尚未產生推薦模型績效")
        elif (recommendation_backtest["status"] == "ok").any():
            preview = recommendation_backtest[recommendation_backtest["status"] == "ok"].iloc[0]
            st.metric("Top N", int(preview.get("top_n", 0)))
            st.write("累積報酬：", _fmt_pct(preview.get("cumulative_return")))
            st.write("勝率：", _fmt_pct(preview.get("win_rate")))
        else:
            st.warning("回測尚未產生結果：insufficient_history")

    _render_stock_lookup(stock_view, selected_stock_query, top_n, stock_alpha_breakdown)
    _build_sector_cards(sector_view)

    st.markdown("---")
    tab_reco, tab_trend, tab_chart, tab_sector, tab_stock, tab_backtest = st.tabs(["推薦引擎", "推薦股Trend", "泡泡圖", "板塊排行", "個股查詢", "回測"])

    with tab_reco:
        st.subheader("候選清單")
        recs = _filter_recommendations(recommendations, selected_market)
        if recs.empty:
            st.info("目前沒有符合條件的候選清單")
        else:
            sector_options = ["全部"] + sorted(recs["industry"].dropna().astype(str).unique().tolist())
            rec_sector = st.selectbox("產業篩選", sector_options, key="recommendation_sector")
            if rec_sector != "全部":
                recs = _filter_recommendations(recommendations, selected_market, rec_sector)
            _render_recommendation_cards(
                recs,
                "全部",
                limit=min(max(top_n, 10), 30),
                top_overall_only=False,
                context="tab_reco",
            )
            table_cols = [
                "stock_code",
                "stock_name",
                "market",
                "industry",
                "alpha_score_total",
                "main_buy_component",
                "foreign_component",
                "trust_component",
                "trade_value_component",
                "momentum_component",
                "risk_penalty",
                "suggested_status",
            ]
            show_cols = [c for c in table_cols if c in recs.columns]
            table = recs.head(min(max(top_n, 10), 100))[show_cols].copy()
            st.dataframe(
                table.rename(
                    columns={
                        "stock_code": "代號",
                        "stock_name": "名稱",
                        "market": "市場",
                        "industry": "產業",
                        "alpha_score_total": "Alpha Score",
                        "main_buy_component": "主力分數",
                        "foreign_component": "外資分數",
                        "trust_component": "投信分數",
                        "trade_value_component": "成交值分數",
                        "momentum_component": "動能分數",
                        "risk_penalty": "風險扣分",
                        "suggested_status": "建議狀態",
                    }
                ),
                width="stretch",
                hide_index=True,
            )

    with tab_trend:
        _render_top10_trend_panel(recommendations, selected_market)

    with tab_chart:
        st.subheader("板塊資金象限")
        if not sectorrotation_sector.empty:
            _render_sectorrotation_reference(sectorrotation_sector, sectorrotation_stock)
        else:
            if not sector_view.empty:
                st.caption("X 軸：近 5 日三方買賣超（股數） | Y 軸：資金加速度（股數/日）")
            _render_bubble_section(sector_view)

    with tab_sector:
        st.subheader("板塊排行榜")
        if not sectorrotation_sector.empty:
            st.markdown("#### 對照站板塊排行")
            _render_sectorrotation_reference(sectorrotation_sector, sectorrotation_stock)
            st.markdown("#### 官方產業排行")
        if sector_view.empty:
            st.info("暫無板塊資料")
        else:
            sector_mode = st.radio(
                "排序方式",
                ["CP值", "主力流入排行", "最新漲跌觀察"],
                horizontal=True,
            )
            if sector_mode == "CP值":
                ranking = sector_view.sort_values("cp_score", ascending=False)
                title_note = "CP = 近5日主力流入 + 行業 Alpha 綜合分數"
            elif sector_mode == "主力流入排行":
                ranking = sector_view.sort_values("net_5d", ascending=False)
                title_note = "依近5日三方淨流入（股數）排序"
            else:
                # 與市場觀測邏輯簡化為：只列出近5日淨流入為正但加速度偏弱或退潮中的板塊
                mkt_status = _latest_market_status(_load_df("data/processed/index.parquet"))
                is_down = any(v.startswith("-") for v in mkt_status.values())
                if not is_down:
                    ranking = pd.DataFrame(columns=sector_view.columns)
                    title_note = "尚未進入下跌市況，暫不顯示抄底榜"
                else:
                    ranking = sector_view.sort_values("net_5d", ascending=True)
                    title_note = "市場轉弱時，觀察逆勢資金進入的板塊"
            if title_note:
                st.caption(title_note)

            if ranking.empty:
                st.info("當前條件下未找到板塊")
            else:
                ranking_show = ranking[
                    [
                        "industry",
                        "market",
                        "net_5d",
                        "net_20d",
                        "accel",
                        "sector_alpha_score",
                        "category",
                    ]
                ].copy()
                ranking_show["category"] = ranking_show["category"].map(lambda x: CAT_META[x]["label"] if x in CAT_META else x)
                ranking_show["five_day_net"] = ranking_show["net_5d"].apply(_fmt_shares)
                ranking_show["twenty_day_net"] = ranking_show["net_20d"].apply(_fmt_shares)
                ranking_show["accel"] = ranking_show["accel"].apply(lambda x: _fmt_number(x, 2))
                ranking_show["sector_alpha_score"] = ranking_show["sector_alpha_score"].apply(lambda x: _fmt_number(x, 4))
                if "moneydj_flow_rate_pct" in ranking_show.columns:
                    ranking_show["moneydj_flow_rate_pct"] = ranking_show["moneydj_flow_rate_pct"].apply(
                        lambda x: "N/A" if pd.isna(x) else f"{float(x):.2f}%"
                    )
                for col in [
                    "moneydj_flow_rate_5d_avg_pct",
                    "moneydj_flow_rate_20d_avg_pct",
                    "moneydj_flow_rate_accel_pct",
                    "moneydj_relative_strength_20d_pct",
                ]:
                    if col in ranking_show.columns:
                        ranking_show[col] = ranking_show[col].apply(
                            lambda x: "N/A" if pd.isna(x) else f"{float(x):.2f}%"
                        )
                if "moneydj_validation_status" in ranking_show.columns:
                    ranking_show["moneydj_validation_status"] = ranking_show["moneydj_validation_status"].map(
                        {"pass": "通過", "warning": "注意", "fail": "失敗"}
                    ).fillna("N/A")

                sector_columns = [
                    "industry",
                    "market",
                    "category",
                    "five_day_net",
                    "twenty_day_net",
                    "accel",
                    "sector_alpha_score",
                ]
                sector_rename = {
                    "industry": "產業",
                    "market": "市場",
                    "category": "象限",
                    "five_day_net": "近5日淨流入",
                    "twenty_day_net": "近20日淨流入",
                    "accel": "加速度",
                    "sector_alpha_score": "Sector Alpha",
                }
                if "moneydj_flow_rate_pct" in ranking_show.columns:
                    sector_columns.append("moneydj_flow_rate_pct")
                    sector_rename["moneydj_flow_rate_pct"] = "MoneyDJ流向率(補充)"
                optional_moneydj_columns = [
                    ("moneydj_flow_rate_5d_avg_pct", "MoneyDJ 5日均值"),
                    ("moneydj_flow_rate_20d_avg_pct", "MoneyDJ 20日均值"),
                    ("moneydj_flow_rate_accel_pct", "MoneyDJ加速度"),
                    ("moneydj_relative_strength_20d_pct", "MoneyDJ相對強弱20日"),
                    ("moneydj_validation_status", "MoneyDJ驗證"),
                ]
                for col, label in optional_moneydj_columns:
                    if col in ranking_show.columns:
                        sector_columns.append(col)
                        sector_rename[col] = label
                st.dataframe(
                    ranking_show[sector_columns].rename(columns=sector_rename),
                    width="stretch",
                    hide_index=True,
                )

                sectors = sorted(ranking_show["industry"].astype(str).head(20).tolist())
                selected_sector = st.selectbox("快速查看板塊股票", sectors)
                if selected_sector:
                    _show_sector_stock_detail(stock_view, selected_sector, selected_market, recommendations)

    with tab_stock:
        st.subheader("個股查詢")
        if stock_view.empty:
            if selected_stock_query:
                st.info("尚未收錄此股票，或今日資料尚未更新")
            else:
                st.info("請在左側輸入股票代號或名稱")
        else:
            _render_stock_lookup(stock_view, selected_stock_query, top_n, stock_alpha_breakdown)

    with tab_backtest:
        _render_backtest_panel(recommendation_backtest)
        if alpha_mode.startswith("Alpha v3") and not factor_effectiveness.empty:
            st.subheader("最有效因子排名")
            st.dataframe(factor_effectiveness.head(30), width="stretch", hide_index=True)
            numeric = factor_effectiveness[["ic", "rank_ic", "top_minus_bottom", "effectiveness_score"]].apply(pd.to_numeric, errors="coerce")
            if not numeric.empty:
                st.subheader("因子相關性熱力圖")
                st.dataframe(numeric.corr(), width="stretch")


def _show_sector_stock_detail(
    stock_view: pd.DataFrame,
    sector: str,
    market_filter: str,
    recommendations: pd.DataFrame | None = None,
) -> None:
    if stock_view.empty:
        return

    s = stock_view[stock_view["industry"] == sector].copy()
    if market_filter != "全部":
        s = s[s["market"] == market_filter]
    if s.empty:
        st.warning("此板塊目前缺少個股資料")
        return

    st.markdown("<div class='sector-card'>", unsafe_allow_html=True)
    st.markdown(f"### {sector} 明細")
    if recommendations is not None and not recommendations.empty:
        sector_recs = _filter_recommendations(recommendations, market_filter, sector).head(10)
        if not sector_recs.empty:
            st.markdown("#### 產業內推薦股")
            _render_recommendation_cards(
                sector_recs,
                "全部",
                limit=min(10, len(sector_recs)),
                top_overall_only=False,
                context=f"sector_{sector}",
            )
    s_show = s.copy()
    s_show["three_party_net_shares"] = s_show["three_party_net_shares"].apply(_fmt_shares)
    s_show["flow_rate"] = s_show["flow_rate"].apply(lambda x: _fmt_number(x * 100, 2) + "%")
    s_show["trade_volume"] = s_show["trade_volume"].apply(_fmt_shares)

    st.dataframe(
        s_show[
            ["stock_code", "stock_name", "market", "three_party_net_shares", "trade_volume", "close", "flow_rate", "stock_alpha_score"]
        ].rename(
            columns={
                "stock_code": "代號",
                "stock_name": "名稱",
                "market": "市場",
                "three_party_net_shares": "三方淨流入",
                "trade_volume": "成交量",
                "close": "收盤價",
                "flow_rate": "流向",
                "stock_alpha_score": "Alpha",
            }
        ),
        width="stretch",
        hide_index=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    run_streamlit_app()
