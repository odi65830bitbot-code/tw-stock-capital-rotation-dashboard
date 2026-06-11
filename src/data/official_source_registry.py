"""官方資料來源註冊表.

本模組集中管理 TWSE / TPEX 的官方來源，包含:
- 來源 endpoint（JSON 優先）
- 官方 CSV fallback endpoint
- 資料欄位日期欄位名稱
- 每個資料集對應欄位對應/格式檢核線索
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SourceConfig:
    name: str
    market: str  # "twse" / "tpex"
    json_url: str
    csv_url: str
    date_key: str
    code_field: str
    name_field: str
    date_suffix: str  # for raw folder naming
    csv_format_note: str = ""
    supports_query_date: bool = True
    query_date_format: Literal["roc", "gregorian", "none"] = "none"


TWSE_DAILY_PRICE = SourceConfig(
    name="twse_daily_price",
    market="twse",
    json_url="https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date}&type=ALLBUT0999&response=json",
    # 先嘗試官方網站 JSON；fallback 用官方網站 CSV。
    csv_url="https://www.twse.com.tw/exchangeReport/MI_INDEX?response=csv&date={date}&type=ALLBUT0999",
    date_key="Date",
    code_field="Code",
    name_field="Name",
    date_suffix="twse",
    csv_format_note="twse-mi-index-daily-close",
    supports_query_date=True,
    query_date_format="gregorian",
)


TWSE_INSTITUTION_FLOW = SourceConfig(
    name="twse_institutional_flow",
    market="twse",
    json_url="https://www.twse.com.tw/fund/T86?response=json&date={date}&selectType=ALL",
    csv_url="https://www.twse.com.tw/fund/T86?response=csv&date={date}&selectType=ALL",
    date_key="date",
    code_field="證券代號",
    name_field="證券名稱",
    date_suffix="twse",
    supports_query_date=True,
    query_date_format="gregorian",
)


TWSE_INSTITUTION_AMOUNT = SourceConfig(
    name="twse_institutional_amount",
    market="twse",
    json_url="https://www.twse.com.tw/fund/BFI82U?response=json&dayDate={date}&type=day",
    csv_url="https://www.twse.com.tw/fund/BFI82U?response=csv&dayDate={date}&type=day",
    date_key="date",
    code_field="單位名稱",  # 這個資料集是彙總表，沒有證券代碼；由流程直接補上 pseudo_code
    name_field="單位名稱",
    date_suffix="twse",
    supports_query_date=True,
    query_date_format="gregorian",
)


TWSE_SECTOR_CLASSIFICATION = SourceConfig(
    name="twse_sector_classification",
    market="twse",
    json_url="https://openapi.twse.com.tw/v1/opendata/t187ap14_L",
    csv_url="https://openapi.twse.com.tw/v1/opendata/t187ap14_L?download=csv",
    date_key="出表日期",
    code_field="公司代號",
    name_field="公司名稱",
    date_suffix="twse",
    supports_query_date=False,
    query_date_format="none",
)


TWSE_INDEX = SourceConfig(
    name="twse_index",
    market="twse",
    json_url="https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date={date}&response=json",
    csv_url="https://www.twse.com.tw/exchangeReport/FMTQIK?response=csv&date={date}",
    date_key="date",
    code_field="發行量加權股價指數",
    name_field="發行量加權股價指數",
    date_suffix="twse",
    supports_query_date=True,
    query_date_format="gregorian",
)


TPEX_DAILY_PRICE = SourceConfig(
    name="tpex_daily_price",
    market="tpex",
    json_url="https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes",
    csv_url="https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes",
    date_key="Date",
    code_field="SecuritiesCompanyCode",
    name_field="CompanyName",
    date_suffix="tpex",
    csv_format_note="accept text/csv",
    supports_query_date=False,
    query_date_format="none",
)


TPEX_INSTITUTION_FLOW = SourceConfig(
    name="tpex_institutional_flow",
    market="tpex",
    json_url="https://www.tpex.org.tw/openapi/v1/tpex_3insti_trading",
    csv_url="https://www.tpex.org.tw/openapi/v1/tpex_3insti_trading",
    date_key="Date",
    code_field="SecuritiesCompanyCode",
    name_field="CompanyName",
    date_suffix="tpex",
    csv_format_note="accept text/csv",
    supports_query_date=False,
    query_date_format="none",
)


TPEX_INSTITUTION_AMOUNT = SourceConfig(
    name="tpex_institutional_amount",
    market="tpex",
    json_url="https://www.tpex.org.tw/openapi/v1/tpex_3insti_summary",
    csv_url="https://www.tpex.org.tw/openapi/v1/tpex_3insti_summary",
    date_key="Date",
    code_field="Investor",
    name_field="Investor",
    date_suffix="tpex",
    csv_format_note="accept text/csv",
    supports_query_date=False,
    query_date_format="none",
)


TPEX_SECTOR_CLASSIFICATION = SourceConfig(
    name="tpex_sector_classification",
    market="tpex",
    json_url="https://www.tpex.org.tw/openapi/v1/tpex_index_consti",
    csv_url="https://www.tpex.org.tw/openapi/v1/tpex_index_consti",
    date_key="Date",
    code_field="SecuritiesCompanyCode",
    name_field="CompanyName",
    date_suffix="tpex",
    csv_format_note="accept text/csv",
    supports_query_date=False,
    query_date_format="none",
)


TPEX_INDEX = SourceConfig(
    name="tpex_index",
    market="tpex",
    json_url="https://www.tpex.org.tw/openapi/v1/tpex_index",
    csv_url="https://www.tpex.org.tw/openapi/v1/tpex_index",
    date_key="Date",
    code_field="TAIEX",
    name_field="Date",
    date_suffix="tpex",
    csv_format_note="accept text/csv",
    supports_query_date=False,
    query_date_format="none",
)


TPEX_50_INDEX = SourceConfig(
    name="tpex_50_index",
    market="tpex",
    json_url="https://www.tpex.org.tw/openapi/v1/tpex50_index",
    csv_url="https://www.tpex.org.tw/openapi/v1/tpex50_index",
    date_key="Date",
    code_field="TPEx50Index",
    name_field="TPEx50TotalReturnIndex",
    date_suffix="tpex",
    csv_format_note="accept text/csv",
    supports_query_date=False,
    query_date_format="none",
)


TWSE_DATASETS = {
    TWSE_DAILY_PRICE.name: TWSE_DAILY_PRICE,
    TWSE_INSTITUTION_FLOW.name: TWSE_INSTITUTION_FLOW,
    TWSE_INSTITUTION_AMOUNT.name: TWSE_INSTITUTION_AMOUNT,
    TWSE_SECTOR_CLASSIFICATION.name: TWSE_SECTOR_CLASSIFICATION,
    TWSE_INDEX.name: TWSE_INDEX,
}

TPEX_DATASETS = {
    TPEX_DAILY_PRICE.name: TPEX_DAILY_PRICE,
    TPEX_INSTITUTION_FLOW.name: TPEX_INSTITUTION_FLOW,
    TPEX_INSTITUTION_AMOUNT.name: TPEX_INSTITUTION_AMOUNT,
    TPEX_SECTOR_CLASSIFICATION.name: TPEX_SECTOR_CLASSIFICATION,
    TPEX_INDEX.name: TPEX_INDEX,
    TPEX_50_INDEX.name: TPEX_50_INDEX,
}


ALL_DATASETS = {**TWSE_DATASETS, **TPEX_DATASETS}
