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

小量真實 API smoke test：

```bash
python3 scripts/update_finmind_data.py --limit 3
```

輸出包含：

- `data/raw/finmind/{dataset}/{YYYYMMDD}/{stock_id}.json`
- `data/cache/finmind/{dataset}/{stock_id}.parquet`
- `data/processed/factors_finmind.parquet`
- `data/processed/stock_alpha_v3.parquet`
- `public/data/factors_latest.json`
- `public/data/backtest_alpha_v3.json`
- `data_quality_report_finmind.json`

## GitHub Actions Secrets

在 GitHub repository settings 加入 secret：

```text
FINMIND_TOKEN
```

不要把 token 寫進 workflow、README、程式碼或前端 JSON。

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
