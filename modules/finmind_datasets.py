from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FinMindDatasetSpec:
    dataset_name: str
    update_frequency: str
    required_fields: tuple[str, ...]
    primary_key: tuple[str, ...]
    date_field: str
    is_premium_optional: bool
    fallback_policy: str


DATASETS: dict[str, FinMindDatasetSpec] = {
    "TaiwanStockInfo": FinMindDatasetSpec(
        "TaiwanStockInfo",
        "daily",
        ("stock_id", "stock_name"),
        ("stock_id",),
        "date",
        False,
        "keep_existing_stock_pool",
    ),
    "TaiwanStockPrice": FinMindDatasetSpec(
        "TaiwanStockPrice",
        "daily_after_close",
        ("date", "stock_id", "close"),
        ("date", "stock_id"),
        "date",
        False,
        "fallback_to_twse_tpex_official_price",
    ),
    "TaiwanStockPER": FinMindDatasetSpec(
        "TaiwanStockPER",
        "daily_after_close",
        ("date", "stock_id"),
        ("date", "stock_id"),
        "date",
        False,
        "mark_unavailable_and_keep_neutral_valuation",
    ),
    "TaiwanStockInstitutionalInvestorsBuySell": FinMindDatasetSpec(
        "TaiwanStockInstitutionalInvestorsBuySell",
        "daily_after_close",
        ("date", "stock_id", "name", "buy", "sell"),
        ("date", "stock_id", "name"),
        "date",
        False,
        "fallback_to_official_institutional_flow",
    ),
    "TaiwanStockTotalInstitutionalInvestors": FinMindDatasetSpec(
        "TaiwanStockTotalInstitutionalInvestors",
        "daily_after_close",
        ("date", "name"),
        ("date", "name"),
        "date",
        False,
        "mark_unavailable",
    ),
    "TaiwanStockShareholding": FinMindDatasetSpec(
        "TaiwanStockShareholding",
        "weekly_or_monthly",
        ("date", "stock_id"),
        ("date", "stock_id"),
        "date",
        True,
        "premium_optional_mark_unavailable",
    ),
    "TaiwanStockMarginPurchaseShortSale": FinMindDatasetSpec(
        "TaiwanStockMarginPurchaseShortSale",
        "daily_after_close",
        ("date", "stock_id"),
        ("date", "stock_id"),
        "date",
        False,
        "mark_unavailable_and_keep_neutral_credit",
    ),
    "TaiwanStockTotalMarginPurchaseShortSale": FinMindDatasetSpec(
        "TaiwanStockTotalMarginPurchaseShortSale",
        "daily_after_close",
        ("date",),
        ("date",),
        "date",
        False,
        "mark_unavailable",
    ),
    "TaiwanStockSecuritiesLending": FinMindDatasetSpec(
        "TaiwanStockSecuritiesLending",
        "daily_after_close",
        ("date", "stock_id"),
        ("date", "stock_id"),
        "date",
        True,
        "premium_optional_mark_unavailable",
    ),
    "TaiwanStockTradingDailyReport": FinMindDatasetSpec(
        "TaiwanStockTradingDailyReport",
        "daily_after_close",
        ("date", "stock_id"),
        ("date", "stock_id"),
        "date",
        True,
        "premium_optional_mark_unavailable",
    ),
    "TaiwanStockFinancialStatements": FinMindDatasetSpec(
        "TaiwanStockFinancialStatements",
        "quarterly",
        ("date", "stock_id"),
        ("date", "stock_id"),
        "date",
        False,
        "mark_unavailable_and_keep_neutral_quality",
    ),
    "TaiwanStockBalanceSheet": FinMindDatasetSpec(
        "TaiwanStockBalanceSheet",
        "quarterly",
        ("date", "stock_id"),
        ("date", "stock_id"),
        "date",
        False,
        "mark_unavailable_and_keep_neutral_quality",
    ),
    "TaiwanStockCashFlowsStatement": FinMindDatasetSpec(
        "TaiwanStockCashFlowsStatement",
        "quarterly",
        ("date", "stock_id"),
        ("date", "stock_id"),
        "date",
        False,
        "mark_unavailable_and_keep_neutral_quality",
    ),
    "TaiwanStockDividend": FinMindDatasetSpec(
        "TaiwanStockDividend",
        "monthly_or_event",
        ("date", "stock_id"),
        ("date", "stock_id"),
        "date",
        False,
        "mark_unavailable_and_keep_neutral_valuation",
    ),
    "TaiwanStockMonthRevenue": FinMindDatasetSpec(
        "TaiwanStockMonthRevenue",
        "monthly",
        ("date", "stock_id", "revenue"),
        ("date", "stock_id"),
        "date",
        False,
        "mark_unavailable_and_keep_neutral_revenue",
    ),
    "TaiwanStockDelisting": FinMindDatasetSpec(
        "TaiwanStockDelisting",
        "monthly_or_event",
        ("date", "stock_id"),
        ("date", "stock_id"),
        "date",
        False,
        "mark_unavailable",
    ),
}


DAILY_AFTER_CLOSE_DATASETS = tuple(
    name for name, spec in DATASETS.items() if spec.update_frequency == "daily_after_close"
)


def get_dataset_spec(dataset_name: str) -> FinMindDatasetSpec:
    try:
        return DATASETS[dataset_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported FinMind dataset: {dataset_name}") from exc
