# macOS 本機每日更新設定

目標：每天台灣時間 06:00 與 15:30 執行官方資料優先更新。

## 手動測試一次

在專案根目錄執行：

```bash
cd /Users/maxyu/Documents/台股資金網站
python3 scripts/run_update_once.py
```

未指定日期時，腳本會依台北時間自動選擇「最新已收盤交易日」：

- 每天 `06:00`：補抓前一個完整交易日。
- 每天 `15:30`：盤後更新；官方資料已可用時抓當天，尚未可用時保留前一個完整交易日。
- 週末：抓前一個週五。

若要指定日期：

```bash
python3 scripts/run_update_once.py --date 20260605
```

## 已設定的 macOS 每日更新

本機目前使用 macOS `launchd`，不是 `crontab`。原因是這台 Mac 的 `crontab` 寫入程序會卡住，改用 LaunchAgent 比較穩定。

已建立：

```text
~/Library/LaunchAgents/com.maxyu.tw-stock-daily-update.plist
```

執行時間：

```text
每天 06:00
每天 15:30
```

執行腳本：

```bash
/Users/maxyu/tw-stock-capital-rotation-dashboard/scripts/run_daily_update.sh
```

`/Users/maxyu/tw-stock-capital-rotation-dashboard` 是指向專案資料夾的英文路徑捷徑，用來避免 macOS `launchd` 在中文路徑上出現轉碼失敗。

輸出 log：

```text
logs/launchd_daily_update.out.log
logs/launchd_daily_update.err.log
logs/update_YYYYMMDD.log
```

如要手動重新載入排程：

```bash
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.maxyu.tw-stock-daily-update.plist" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.maxyu.tw-stock-daily-update.plist"
launchctl enable "gui/$(id -u)/com.maxyu.tw-stock-daily-update"
```

## 檢查輸出

更新後應該看到：

```text
logs/update_YYYYMMDD.log
data_quality_report.json
data/processed/daily_price.parquet
data/processed/institutional_flow.parquet
data/processed/sector_flow.parquet
data/processed/stock_alpha.parquet
data/processed/recommendations.parquet
public/data/market_latest.json
public/data/sector_latest.json
public/data/stock_alpha_latest.json
public/data/recommendations_latest.json
public/data/trends/{推薦股代號}.json
```

## 每日狀態檢查

不更新資料，只檢查排程、品質報告與 Dashboard 公開資料日期：

```bash
cd /Users/maxyu/Documents/台股資金網站
scripts/check_daily_update_status.sh
```

這個檢查不會讀取或輸出 `FINMIND_API_TOKEN`。

## 注意

- Streamlit 不負責排程，只讀取 `data/processed` 與 `public/data`。
- 本機使用 `launchd` 排程，不依賴 `crontab`。
- TWSE / TPEX 官方資料失敗會寫入 `logs/update_YYYYMMDD.log`。
- `data_quality_report.json` 會檢查 TWSE / TPEX 最新交易日是否一致；不一致時不能視為完整更新。
- MoneyDJ 只作補充資料，不會替代官方資料。

## FinMind 補充指標

FinMind 只作為補充資料來源，不取代 TWSE / TPEX 官方主資料。

本機手動執行前可先設定：

```bash
export FINMIND_API_TOKEN="your_finmind_api_token_here"
python3 scripts/run_update_once.py --date 20260608
```

目前接入的補充指標：

- 月營收 YoY / MoM，寫入 `revenue_component`。
- PER / PBR / 殖利率，寫入 `quality_component`。
- 輸出檔案：`data/processed/finmind_composite_indicators.parquet`。

注意：請不要把真實 Token 寫進 Git、README、前端程式碼或公開文件。
