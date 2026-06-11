from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
URL = "https://sectorrotation.netlify.app/data/latest.json"
LOGGER = logging.getLogger("sectorrotation_reference")


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _records_from_reference(payload: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    sectors = payload.get("sectors") or []
    stock_data = payload.get("stock_data") or {}
    date_value = payload.get("date")
    sector_rows: list[dict[str, Any]] = []
    stock_rows: list[dict[str, Any]] = []

    for rank, sector in enumerate(sectors, start=1):
        stocks = [str(code).strip() for code in sector.get("stocks", []) if str(code).strip()]
        sector_rows.append(
            {
                "trade_date": date_value,
                "rank": rank,
                "sector_name": sector.get("name"),
                "stock_count": len(stocks),
                "stocks": stocks,
                "net_1d_yi": sector.get("net_1d_yi"),
                "net_5d_yi": sector.get("net_5d_yi"),
                "net_20d_yi": sector.get("net_20d_yi"),
                "position": sector.get("position"),
                "chg_1d": sector.get("chg_1d"),
                "chg_5d": sector.get("chg_5d"),
                "is_bottom_fishing": sector.get("is_bottom_fishing"),
                "bottom_score": sector.get("bottom_score"),
                "source": URL,
            }
        )
        for code in stocks:
            detail = stock_data.get(code, {}) if isinstance(stock_data, dict) else {}
            stock_rows.append(
                {
                    "trade_date": date_value,
                    "sector_rank": rank,
                    "sector_name": sector.get("name"),
                    "stock_code": code,
                    "chg_1d": detail.get("chg_1d"),
                    "net_1d_yi": detail.get("net_1d_yi"),
                    "source": URL,
                }
            )

    return pd.DataFrame(sector_rows), pd.DataFrame(stock_rows)


def _write_unavailable(reason: str) -> None:
    public_dir = ROOT / "public" / "data"
    public_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": URL,
        "status": "unavailable",
        "reason": reason,
        "as_of_date": None,
        "market_chg_1d": None,
        "is_market_down": None,
        "sectors": [],
        "stock_data": [],
    }
    (public_dir / "sectorrotation_latest.json").write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        resp = requests.get(URL, timeout=30, verify=False)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        _write_unavailable(reason)
        LOGGER.warning("sectorrotation reference unavailable: %s", reason)
        return 0

    date_value = str(payload.get("date") or datetime.now().date().isoformat())
    day_key = date_value.replace("-", "")
    raw_dir = ROOT / "data" / "raw" / "sectorrotation" / day_key
    processed_dir = ROOT / "data" / "processed"
    public_dir = ROOT / "public" / "data"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)

    (raw_dir / "latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    sector_df, stock_df = _records_from_reference(payload)
    sector_df.to_parquet(processed_dir / "sectorrotation_sector.parquet", index=False)
    stock_df.to_parquet(processed_dir / "sectorrotation_stock.parquet", index=False)

    public_payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": URL,
        "status": "ok",
        "source_updated_at": payload.get("updated_at"),
        "as_of_date": payload.get("date"),
        "market_chg_1d": payload.get("market_chg_1d"),
        "is_market_down": payload.get("is_market_down"),
        "sectors": sector_df.to_dict(orient="records"),
        "stock_data": stock_df.to_dict(orient="records"),
    }
    (public_dir / "sectorrotation_latest.json").write_text(
        json.dumps(_json_safe(public_payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    LOGGER.info("wrote sectorrotation reference sectors=%s stock_rows=%s", len(sector_df), len(stock_df))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
