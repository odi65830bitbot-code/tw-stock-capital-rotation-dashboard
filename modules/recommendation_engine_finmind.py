from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


ALLOWED_STATUS = {"觀察", "分批觀察", "等待確認", "過熱", "避開"}
FORBIDDEN_WORDS = ("買進", "賣出", "必漲", "明牌", "保證獲利")


def _num(row: pd.Series, col: str, default: float = 0.0) -> float:
    value = pd.to_numeric(pd.Series([row.get(col, default)]), errors="coerce").iloc[0]
    return float(default if pd.isna(value) else value)


def _recommendation_type(row: pd.Series) -> str:
    if _num(row, "risk_penalty_total") >= 30:
        return "避開" if _num(row, "stock_alpha_v3") < 45 else "過熱觀察"
    if _num(row, "sector_alpha") >= 70 and _num(row, "momentum_score") >= 65:
        return "主線強勢股"
    if _num(row, "sector_alpha") >= 55 and _num(row, "momentum_score") < 65 and _num(row, "main_force_proxy") >= 60:
        return "早期輪動股"
    if _num(row, "revenue_score") >= 70 and _num(row, "quality_score") >= 60:
        return "基本面加速股"
    if _num(row, "foreign_score") >= 65 and _num(row, "trust_score") >= 65:
        return "法人同步股"
    if _num(row, "quality_score") >= 70 and _num(row, "valuation_score") >= 60:
        return "防守資金股"
    return "等待確認"


def _status(row: pd.Series, rec_type: str) -> str:
    alpha = _num(row, "stock_alpha_v3")
    risk = _num(row, "risk_penalty_total")
    confidence = _num(row, "confidence_score")
    if rec_type == "避開" or alpha < 35:
        return "避開"
    if risk >= 30:
        return "過熱"
    if confidence < 45:
        return "等待確認"
    if alpha >= 70:
        return "觀察"
    if alpha >= 55:
        return "分批觀察"
    return "等待確認"


def _clean_text(text: str) -> str:
    out = text
    for word in FORBIDDEN_WORDS:
        out = out.replace(word, "觀察")
    return out


def build_recommendation_observations(
    alpha_v3: pd.DataFrame,
    backtest: pd.DataFrame | None = None,
    *,
    top_n: int = 50,
) -> pd.DataFrame:
    if alpha_v3.empty:
        return pd.DataFrame()
    df = alpha_v3.copy()
    if "stock_id" not in df.columns and "stock_code" in df.columns:
        df["stock_id"] = df["stock_code"].astype(str)
    df["stock_alpha_v3"] = pd.to_numeric(df["stock_alpha_v3"], errors="coerce").fillna(0)
    df = df.sort_values("stock_alpha_v3", ascending=False).head(top_n).copy()
    rows: list[dict[str, Any]] = []
    backtest_win = pd.NA
    backtest_avg = pd.NA
    backtest_mdd = pd.NA
    if backtest is not None and not backtest.empty:
        ok = backtest[backtest.get("status", "") == "ok"] if "status" in backtest.columns else backtest
        if not ok.empty:
            best = ok.sort_values("top_n").iloc[0]
            backtest_win = best.get("win_rate", pd.NA)
            backtest_avg = best.get("avg_return_20d", pd.NA)
            backtest_mdd = best.get("max_drawdown", pd.NA)
    for _, row in df.iterrows():
        rec_type = _recommendation_type(row)
        status = _status(row, rec_type)
        risks = row.get("risk_tags", [])
        if not isinstance(risks, list):
            risks = [str(risks)] if str(risks or "") else []
        reasons = row.get("alpha_reason_codes", [])
        if not isinstance(reasons, list):
            reasons = [str(reasons)] if str(reasons or "") else []
        summary = _clean_text(
            f"{row.get('stock_id')} {row.get('stock_name', '')} Alpha v3 {_num(row, 'stock_alpha_v3'):.1f}，"
            f"{rec_type}，狀態為{status}。"
        )
        rows.append(
            {
                "stock_id": str(row.get("stock_id", "")),
                "trade_date": row.get("trade_date", ""),
                "stock_name": row.get("stock_name", ""),
                "market": row.get("market", ""),
                "sector": row.get("sector", row.get("industry", "")),
                "recommendation_type": rec_type,
                "stock_alpha_v3": _num(row, "stock_alpha_v3"),
                "sector_alpha": _num(row, "sector_alpha", 50),
                "main_force_proxy": _num(row, "main_force_proxy", 50),
                "foreign_score": _num(row, "foreign_score", 50),
                "trust_score": _num(row, "trust_score", 50),
                "revenue_score": _num(row, "revenue_score", 50),
                "quality_score": _num(row, "quality_score", 50),
                "valuation_score": _num(row, "valuation_score", 50),
                "momentum_score": _num(row, "momentum_score", 50),
                "liquidity_score": _num(row, "liquidity_score", 50),
                "risk_penalty": _num(row, "risk_penalty_total", 0),
                "confidence_score": _num(row, "confidence_score", 0),
                "summary_reason": summary,
                "reason_1": _clean_text(reasons[0] if len(reasons) > 0 else "Alpha v3 多因子分數進入觀察區間"),
                "reason_2": _clean_text(reasons[1] if len(reasons) > 1 else "法人、量價或基本面訊號仍需追蹤"),
                "reason_3": _clean_text(reasons[2] if len(reasons) > 2 else "僅列為觀察標的，需等待資料延續確認"),
                "main_risk_1": risks[0] if len(risks) > 0 else "大盤與產業輪動變化",
                "main_risk_2": risks[1] if len(risks) > 1 else "資料完整度與公告延遲",
                "backtest_win_rate": backtest_win,
                "backtest_avg_return_20d": backtest_avg,
                "backtest_max_drawdown": backtest_mdd,
                "status": status if status in ALLOWED_STATUS else "等待確認",
            }
        )
    return pd.DataFrame(rows)


def write_recommendations_v3(recommendations: pd.DataFrame, *, processed_path: Path, public_json_path: Path) -> None:
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    public_json_path.parent.mkdir(parents=True, exist_ok=True)
    recommendations.to_parquet(processed_path, index=False)
    payload = {
        "generated_at": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "records": recommendations.replace({pd.NA: None}).to_dict(orient="records"),
        "disclaimer": "推薦分類僅代表觀察標的，不包含買賣建議、明牌或獲利保證。",
    }
    public_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
