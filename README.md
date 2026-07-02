# 台股產業輪動 / Alpha Dashboard

TWSE / TPEX 官方資料是每日盤後事實來源；FinMind 只作為歷史資料、月營收、財報、法人、融資融券與回測的補強來源。所有推薦輸出都只代表「觀察標的」，不是買賣建議。

## FinMind Token

1. 到 FinMind 官網申請 API token。
2. 本機建立 `.env`，不要 commit：

```bash
cp .env.example .env
```

3. 在 `.env` 填入：

```bash
FINMIND_TOKEN=your_token_here
```

也可以只在 shell session 設定：

```bash
export FINMIND_TOKEN="your_token_here"
```

## 本機更新

官方資料每日更新：

```bash
python3 scripts/update_daily.py
```

FinMind 補強資料更新：

```bash
python3 scripts/update_finmind_data.py
```

ETF 成份股與權重資料更新：

```bash
python3 scripts/update_etf_holdings.py
python3 scripts/build_formal_json_outputs.py
```

`scripts/update_etf_holdings.py` 會讀取 `data/raw/etf_holdings/**/*.csv` 或 `data/raw/etf_holdings/**/*.json`，標準化後寫入 `data/processed/etf_holdings.parquet`。欄位可使用英文或中文常見名稱，例如 `ETF代號`、`ETF名稱`、`成分股代號`、`成分股名稱`、`權重`、`股數`、`市值`、`資料日期`。來源檔請優先使用 TWSE / TPEX、投信或 ETF 官方匯出資料，不要把不明來源覆蓋成官方資料。

小量真實 API smoke test：

```bash
python3 scripts/update_finmind_data.py --limit 3
```

產生前端靜態 JSON：

```bash
python3 scripts/build_formal_json_outputs.py
```

輸出包含：

- `data/raw/finmind/{dataset}/{YYYYMMDD}/{stock_id}.json`
- `data/cache/finmind/{dataset}/{stock_id}.parquet`
- `data/processed/factors_finmind.parquet`
- `data/processed/stock_alpha_v3.parquet`
- `public/data/factors_latest.json`
- `public/data/backtest_alpha_v3.json`
- `public/data/data_manifest.json`
- `data_quality_report_finmind.json`

## 資料減肥與更新策略

這個網站定位為盤前 / 盤後觀察工具，不做即時盤中輪詢。

- 前端只讀 `public/data/*.json` 與 `public/data/trends/*.json` 靜態檔。
- `stock_alpha_latest.json` / `stock_alpha_v4_latest.json` 只保留 Dashboard 排行摘要，預設前 300 筆。
- `stock_lookup_latest.json` 保留全市場普通股與 ETF 基本字典，只含代號、名稱、產業/ETF 標籤、收盤價、漲跌幅與成交值，支援任意代號查詢。
- `etf_holdings_latest.json` 保留每檔 ETF 的最新成份股、權重、股數與市值；若尚未匯入來源檔，輸出 `warning`，不假造資料。
- `sector_constituents_latest.json` 只保留每個市場 / 產業前 40 檔成分股，避免首頁載入全市場明細。
- 個股深度走勢改讀 `public/data/trends/{stock_id}.json`，需要時才載入。
- `data_manifest.json` 記錄每個 public JSON 的資料日期、筆數、是否截斷與檔案大小。
- `data/raw`、`data/cache`、`data/processed` 是本機或 CI 中間產物，不應作為網站前端載入來源。
- GitHub Actions 使用 cache 保存 `data/processed`，每日 commit 只回寫 `public/data`、品質報告與 `reports`。

可用環境變數調整輸出大小：

```bash
PUBLIC_STOCK_ALPHA_LIMIT=300
SECTOR_CONSTITUENT_PER_GROUP_LIMIT=40
TREND_TOP_N=100
```

## GitHub Actions Secrets

在 GitHub repository settings 加入 secret：

```text
FINMIND_TOKEN
```

不要把 token 寫進 workflow、README、程式碼或前端 JSON。

## 測試策略

- TDD：資料清洗、代號篩選、payload 格式與邊界條件先寫單元測試。
- BDD：使用者查詢情境與資料契約用 Given / When / Then 形式寫在 `tests/test_bdd_*.py`。
- ETF 相關變更至少要跑：

```bash
python3 -m pytest tests/test_bdd_etf_data_contract.py tests/test_update_etf_holdings.py tests/test_update_daily_cleanup.py
```

## API 超限與權限不足

- `config.yaml` 可調整 `batch_size`、`sleep_seconds`、`retry` 與 `request_timeout`。
- Premium 或權限不足 dataset 會標記 `unavailable`，不會中斷 Dashboard。
- TWSE / TPEX 官方資料仍會獨立運作；FinMind 失敗時，Alpha v1 / 官方資料版仍可使用。

## Dashboard

```bash
scripts/start_dashboard.sh
```

預設網址：

```text
http://127.0.0.1:8503
```
