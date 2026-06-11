from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
API_URL = os.getenv("FINMIND_API_URL", "https://api.finmindtrade.com/api/v4/data")
DATASET = "TaiwanFuturesDaily"
INSTITUTIONAL_DATASET = "TaiwanFuturesInstitutionalInvestorsAfterHours"
FUTURES_ID = "TX"
TRADING_SESSION = "after_market"
LOGGER = logging.getLogger("update_txf_after_hours")


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def _load_local_env() -> None:
    _load_env_file(ROOT / "secrets-local" / "finmind.env")
    _load_env_file(ROOT / ".env")


def _token() -> str | None:
    return (
        os.getenv("FINMIND_API_TOKEN")
        or os.getenv("FINMIND_TOKEN")
        or os.getenv("FINMIND_API_KEY")
        or os.getenv("FINMIND_ACCESS_TOKEN")
    )


def _headers() -> dict[str, str]:
    token = _token()
    return {"Authorization": f"Bearer {token}"} if token else {}


def _response_error_message(resp: requests.Response) -> str:
    try:
        payload = resp.json()
        if isinstance(payload, dict):
            return str(payload.get("msg") or payload.get("message") or payload)
    except Exception:
        pass
    text = resp.text.strip()
    return text[:300] if text else resp.reason


def _is_plan_or_permission_error(message: str) -> bool:
    text = message.lower()
    return any(token in text for token in ["permission", "auth", "sponsor", "backer", "vip", "quota", "權限", "會員", "贊助"])


def _request_finmind(params: dict[str, Any], *, retries: int = 3) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(API_URL, headers=_headers(), params=params, timeout=30)
            if not resp.ok:
                raise RuntimeError(f"HTTP {resp.status_code}: {_response_error_message(resp)}")
            payload = resp.json()
            if isinstance(payload, dict) and payload.get("status") not in (None, 200, "200"):
                message = payload.get("msg") or payload.get("message") or payload.get("status")
                raise RuntimeError(f"FinMind status not ok: {message}")
            data = payload.get("data") if isinstance(payload, dict) else payload
            if not isinstance(data, list):
                raise RuntimeError("FinMind payload missing list data")
            return data, payload if isinstance(payload, dict) else {"data": data}
        except Exception as exc:
            last_error = exc
            LOGGER.warning("FinMind request failed attempt=%s/%s dataset=%s error=%s", attempt, retries, params.get("dataset"), type(exc).__name__)
            if attempt < retries:
                time.sleep(min(2**attempt, 8))
    raise RuntimeError(f"FinMind request failed after retries: {last_error}")


def _to_number(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _normalize_futures_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            columns=[
                "date",
                "futures_id",
                "contract_date",
                "open",
                "max",
                "min",
                "close",
                "spread",
                "spread_per",
                "volume",
                "settlement_price",
                "open_interest",
                "trading_session",
                "night_index",
                "is_main_contract",
            ]
        )
    df = pd.DataFrame(rows)
    if "futures_id" in df.columns:
        df = df[df["futures_id"].astype(str) == FUTURES_ID].copy()
    if "trading_session" in df.columns:
        df = df[df["trading_session"].astype(str) == TRADING_SESSION].copy()
    df = _to_number(df, ["open", "max", "min", "close", "spread", "spread_per", "volume", "settlement_price", "open_interest"])
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    if "settlement_price" not in df.columns:
        df["settlement_price"] = pd.NA
    if "close" not in df.columns:
        df["close"] = pd.NA
    settlement = pd.to_numeric(df["settlement_price"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")
    df["night_index"] = settlement.where(settlement.gt(0), close)
    if "volume" in df.columns:
        df["_volume_rank"] = pd.to_numeric(df["volume"], errors="coerce").fillna(-1)
    else:
        df["_volume_rank"] = -1
    df["is_main_contract"] = False
    if not df.empty and "date" in df.columns:
        idx = df.sort_values(["date", "_volume_rank"], ascending=[True, False]).groupby("date", dropna=False).head(1).index
        df.loc[idx, "is_main_contract"] = True
    return df.drop(columns=["_volume_rank"], errors="ignore").sort_values(["date", "is_main_contract", "volume"], ascending=[True, False, False])


def _fetch_futures(start_date: str, end_date: str) -> pd.DataFrame:
    params = {
        "dataset": DATASET,
        "data_id": FUTURES_ID,
        "start_date": start_date,
        "end_date": end_date,
        "trading_session": TRADING_SESSION,
    }
    rows, _ = _request_finmind(params)
    return _normalize_futures_rows(rows)


def _fetch_institutional(start_date: str, end_date: str) -> tuple[pd.DataFrame, str | None, str]:
    params = {
        "dataset": INSTITUTIONAL_DATASET,
        "data_id": FUTURES_ID,
        "start_date": start_date,
        "end_date": end_date,
    }
    try:
        rows, _ = _request_finmind(params, retries=2)
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        status = "permission_or_plan_required" if _is_plan_or_permission_error(message) else "unavailable"
        return pd.DataFrame(), message, status
    df = pd.DataFrame(rows)
    if df.empty:
        return df, None, "empty"
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return df, None, "ok"


def _merge_history(existing_path: Path, incoming: pd.DataFrame) -> pd.DataFrame:
    existing = pd.read_parquet(existing_path) if existing_path.exists() else pd.DataFrame()
    merged = pd.concat([existing, incoming], ignore_index=True)
    keys = [col for col in ["date", "futures_id", "contract_date", "trading_session"] if col in merged.columns]
    if keys:
        merged = merged.drop_duplicates(subset=keys, keep="last")
    return merged.sort_values([c for c in ["date", "futures_id", "contract_date"] if c in merged.columns])


def _json_safe(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if value is pd.NA:
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _write_quality(status: str, row_count: int, latest_date: str | None, institutional_status: str, warnings: list[str], errors: list[str]) -> None:
    path = ROOT / "data_quality_report.json"
    try:
        report = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        report = {}
    report["futures_after_hours"] = {
        "status": status,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": DATASET,
        "futures_id": FUTURES_ID,
        "trading_session": TRADING_SESSION,
        "row_count": row_count,
        "latest_date": latest_date,
        "institutional_status": institutional_status,
        "warnings": warnings,
        "errors": errors,
    }
    path.write_text(json.dumps(_json_safe(report), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def _write_public_json(df: pd.DataFrame, institutional: pd.DataFrame, status: str, institutional_status: str, warnings: list[str], errors: list[str]) -> None:
    public_dir = ROOT / "public" / "data"
    public_dir.mkdir(parents=True, exist_ok=True)
    main = df[df.get("is_main_contract", False).astype(bool)].copy() if not df.empty and "is_main_contract" in df.columns else df.copy()
    main = main.sort_values("date") if "date" in main.columns else main
    latest = main.iloc[-1].to_dict() if not main.empty else None
    records = main.tail(30).to_dict(orient="records") if not main.empty else []
    institutional_records = institutional.tail(30).to_dict(orient="records") if not institutional.empty else []
    payload = {
        "data_timestamp": datetime.now().isoformat(timespec="seconds"),
        "source": "FinMind",
        "source_url": "https://api.finmindtrade.com/api/v4/data",
        "status": status,
        "dataset": DATASET,
        "institutional_dataset": INSTITUTIONAL_DATASET,
        "institutional_status": institutional_status,
        "futures_id": FUTURES_ID,
        "trading_session": TRADING_SESSION,
        "as_of_date": latest.get("date") if isinstance(latest, dict) else None,
        "index_field": "settlement_price if positive else close",
        "selection_method": "main night contract = highest volume per date",
        "latest": latest,
        "records": records,
        "institutional_records": institutional_records,
        "warnings": warnings,
        "errors": errors,
    }
    (public_dir / "futures_after_hours_latest.json").write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Update TX futures after-hours data from FinMind.")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--skip-institutional", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    _load_local_env()

    end = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    start = end - timedelta(days=max(args.days, 1))
    start_date = start.isoformat()
    end_date = end.isoformat()
    processed_dir = ROOT / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    processed_path = processed_dir / "futures_after_hours.parquet"
    institutional_path = processed_dir / "futures_after_hours_institutional.parquet"
    warnings: list[str] = []
    errors: list[str] = []
    institutional_status = "skipped" if args.skip_institutional else "unavailable"

    try:
        incoming = _fetch_futures(start_date, end_date)
        if incoming.empty:
            warnings.append("FinMind returned no TX after-market futures rows")
        history = _merge_history(processed_path, incoming)
        history.to_parquet(processed_path, index=False)
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        history = pd.read_parquet(processed_path) if processed_path.exists() else pd.DataFrame()
        warnings.append("used existing futures_after_hours.parquet fallback" if not history.empty else "no fallback futures data available")

    institutional = pd.DataFrame()
    if not args.skip_institutional:
        inst_incoming, inst_error, institutional_status = _fetch_institutional(start_date, end_date)
        if inst_error:
            warnings.append(f"institutional after-hours unavailable: {inst_error}")
            if institutional_path.exists():
                institutional = pd.read_parquet(institutional_path)
                warnings.append("used existing futures_after_hours_institutional.parquet fallback")
        elif not inst_incoming.empty:
            institutional = _merge_history(institutional_path, inst_incoming)
            institutional.to_parquet(institutional_path, index=False)
        elif institutional_path.exists():
            institutional = pd.read_parquet(institutional_path)
            warnings.append("used existing futures_after_hours_institutional.parquet fallback")

    status = "ok" if not errors and not history.empty else "warning" if not history.empty else "error"
    latest_date = None
    if not history.empty and "date" in history.columns:
        latest_date = str(history["date"].max())
    _write_public_json(history, institutional, status, institutional_status, warnings, errors)
    _write_quality(status, int(len(history)), latest_date, institutional_status, warnings, errors)
    LOGGER.info("finished status=%s rows=%s latest_date=%s", status, len(history), latest_date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
