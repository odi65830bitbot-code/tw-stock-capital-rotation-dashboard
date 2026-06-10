from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from .finmind_datasets import get_dataset_spec

LOGGER = logging.getLogger(__name__)
FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"


@dataclass
class FinMindDatasetResult:
    dataset: str
    dataframe: pd.DataFrame
    records: list[dict[str, Any]]
    raw_json_path: Path
    cache_path: Path
    status: str
    message: str = ""
    premium_optional: bool = False


def _load_dotenv_value(env_file: Path, key: str) -> str:
    if not env_file.exists():
        return ""
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        lhs, rhs = line.split("=", 1)
        if lhs.strip() == key:
            return rhs.strip().strip('"').strip("'")
    return ""


def resolve_finmind_token(env_file: Path | None = None) -> str:
    env_file = env_file or Path(".env")
    token = os.getenv("FINMIND_TOKEN", "").strip()
    if token:
        return token
    token = _load_dotenv_value(env_file, "FINMIND_TOKEN").strip()
    if token:
        return token
    legacy = os.getenv("FINMIND_API_TOKEN", "").strip()
    if legacy:
        return legacy
    return _load_dotenv_value(env_file, "FINMIND_API_TOKEN").strip()


class FinMindClient:
    def __init__(
        self,
        *,
        raw_root: Path = Path("data/raw"),
        cache_root: Path = Path("data/cache"),
        env_file: Path | None = None,
        token: str | None = None,
        timeout: int = 30,
        retry: int = 3,
        sleep_seconds: float = 0.5,
        session: requests.Session | None = None,
    ) -> None:
        self.raw_root = Path(raw_root)
        self.cache_root = Path(cache_root)
        self.env_file = env_file or Path(".env")
        self.token = (token or resolve_finmind_token(self.env_file)).strip()
        self.timeout = int(timeout)
        self.retry = int(retry)
        self.sleep_seconds = float(sleep_seconds)
        self.session = session or requests.Session()
        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.cache_root.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def _require_token(self) -> None:
        if not self.token:
            raise RuntimeError("FINMIND_TOKEN is not configured. Set FINMIND_TOKEN in the shell or local .env.")

    def _paths(self, dataset: str, stock_id: str | None, as_of: date | None) -> tuple[Path, Path]:
        day = (as_of or date.today()).strftime("%Y%m%d")
        safe_stock_id = str(stock_id or "all").strip() or "all"
        raw_path = self.raw_root / "finmind" / dataset / day / f"{safe_stock_id}.json"
        cache_path = self.cache_root / "finmind" / dataset / f"{safe_stock_id}.parquet"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        return raw_path, cache_path

    def fetch_dataset(
        self,
        dataset: str,
        *,
        stock_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        extra_params: dict[str, Any] | None = None,
        as_of: date | None = None,
        allow_unavailable: bool = False,
    ) -> FinMindDatasetResult:
        self._require_token()
        spec = get_dataset_spec(dataset)
        raw_path, cache_path = self._paths(dataset, stock_id, as_of)
        params: dict[str, Any] = {"dataset": dataset}
        if stock_id:
            params["data_id"] = str(stock_id)
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if extra_params:
            params.update(extra_params)

        last_error: Exception | None = None
        for attempt in range(1, self.retry + 1):
            try:
                response = self.session.get(
                    FINMIND_API_URL,
                    params=params,
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=self.timeout,
                )
                if getattr(response, "status_code", 200) in {429, 500, 502, 503, 504}:
                    raise RuntimeError(f"FinMind temporary HTTP {response.status_code}")
                response.raise_for_status()
                payload = response.json()
                data = payload.get("data", []) if isinstance(payload, dict) else []
                if not isinstance(data, list):
                    raise ValueError(f"FinMind {dataset} returned unsupported data payload")
                raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                df = pd.DataFrame(data)
                if not df.empty:
                    df.to_parquet(cache_path, index=False)
                else:
                    pd.DataFrame().to_parquet(cache_path, index=False)
                return FinMindDatasetResult(
                    dataset=dataset,
                    dataframe=df,
                    records=data,
                    raw_json_path=raw_path,
                    cache_path=cache_path,
                    status="ok" if data else "empty",
                    premium_optional=spec.is_premium_optional,
                )
            except Exception as exc:
                last_error = exc
                LOGGER.warning("FinMind %s attempt %s/%s failed: %s", dataset, attempt, self.retry, type(exc).__name__)
                if attempt < self.retry:
                    time.sleep(self.sleep_seconds * attempt)

        message = f"{dataset} unavailable: {type(last_error).__name__ if last_error else 'unknown'}"
        if allow_unavailable or spec.is_premium_optional:
            raw_path.write_text(
                json.dumps({"status": "unavailable", "dataset": dataset, "message": message}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            pd.DataFrame().to_parquet(cache_path, index=False)
            return FinMindDatasetResult(
                dataset=dataset,
                dataframe=pd.DataFrame(),
                records=[],
                raw_json_path=raw_path,
                cache_path=cache_path,
                status="unavailable",
                message=message,
                premium_optional=spec.is_premium_optional,
            )
        raise RuntimeError(message) from last_error

    def batch_fetch(
        self,
        dataset: str,
        stock_ids: list[str],
        *,
        start_date: str,
        end_date: str,
        allow_unavailable: bool = True,
    ) -> list[FinMindDatasetResult]:
        return [
            self.fetch_dataset(
                dataset,
                stock_id=stock_id,
                start_date=start_date,
                end_date=end_date,
                allow_unavailable=allow_unavailable,
            )
            for stock_id in stock_ids
        ]

    def fetch_composite_indicators(self, target_date: date) -> pd.DataFrame:
        if not self.enabled:
            LOGGER.info("FinMind disabled: FINMIND_TOKEN is not configured")
            return pd.DataFrame()

        frames: list[pd.DataFrame] = []
        start_revenue = (pd.Timestamp(target_date) - pd.DateOffset(months=18)).strftime("%Y-%m-%d")
        end_date = target_date.isoformat()
        for dataset, normalizer in [
            ("TaiwanStockMonthRevenue", _normalize_month_revenue),
            ("TaiwanStockPER", _normalize_per_pbr),
        ]:
            try:
                result = self.fetch_dataset(
                    dataset,
                    start_date=start_revenue,
                    end_date=end_date,
                    as_of=target_date,
                    allow_unavailable=True,
                )
                if result.status == "ok":
                    frames.append(normalizer(result.records))
            except Exception as exc:
                LOGGER.warning("FinMind %s unavailable for composite indicators: %s", dataset, type(exc).__name__)
        clean = [df for df in frames if not df.empty]
        if not clean:
            return pd.DataFrame()
        out = clean[0]
        for df in clean[1:]:
            out = out.merge(df, on="stock_code", how="outer")
        out["source"] = "finmind"
        return out.reset_index(drop=True)


def _normalize_month_revenue(records: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty or "stock_id" not in df.columns or "revenue" not in df.columns:
        return pd.DataFrame()
    df["stock_code"] = df["stock_id"].astype(str).str.strip()
    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")
    df = df.dropna(subset=["stock_code", "date", "revenue"]).sort_values(["stock_code", "date"])
    if df.empty:
        return pd.DataFrame()
    latest = df.groupby("stock_code", as_index=False).tail(1).copy()
    latest["finmind_revenue_mom_pct"] = df.groupby("stock_code")["revenue"].pct_change().groupby(df["stock_code"]).tail(1).values * 100
    df["month"] = df["date"].dt.month
    df["year"] = df["date"].dt.year
    yoy = df[["stock_code", "month", "year", "revenue"]].rename(columns={"revenue": "prev_year_revenue"})
    latest["month"] = latest["date"].dt.month
    latest["prev_year"] = latest["date"].dt.year - 1
    latest = latest.merge(
        yoy,
        left_on=["stock_code", "month", "prev_year"],
        right_on=["stock_code", "month", "year"],
        how="left",
    )
    latest["finmind_revenue_yoy_pct"] = (
        (latest["revenue"] - latest["prev_year_revenue"])
        / latest["prev_year_revenue"].where(latest["prev_year_revenue"] > 0)
        * 100
    )
    latest["finmind_revenue_date"] = latest["date"].dt.strftime("%Y-%m-%d")
    return latest[
        ["stock_code", "finmind_revenue_date", "revenue", "finmind_revenue_mom_pct", "finmind_revenue_yoy_pct"]
    ].rename(columns={"revenue": "finmind_month_revenue"})


def _normalize_per_pbr(records: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty or "stock_id" not in df.columns:
        return pd.DataFrame()
    df["stock_code"] = df["stock_id"].astype(str).str.strip()
    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
    df = df.dropna(subset=["stock_code", "date"]).sort_values(["stock_code", "date"])
    rename = {
        "PER": "finmind_per",
        "PBR": "finmind_pbr",
        "dividend_yield": "finmind_dividend_yield_pct",
        "DividendYield": "finmind_dividend_yield_pct",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    for col in ["finmind_per", "finmind_pbr", "finmind_dividend_yield_pct"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    latest = df.groupby("stock_code", as_index=False).tail(1).copy()
    latest["finmind_valuation_date"] = latest["date"].dt.strftime("%Y-%m-%d")
    cols = ["stock_code", "finmind_valuation_date", "finmind_per", "finmind_pbr", "finmind_dividend_yield_pct"]
    return latest[[c for c in cols if c in latest.columns]].reset_index(drop=True)
