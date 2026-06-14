# Phase 5: 高勝率量化與情緒選股模型實作指南

## 目標
徹底重構 AI Alpha 選股引擎。整合國內外財經數據、資金流、社群情緒、盈餘(由黑翻紅/利潤大幅成長)、合約負債(預收利潤)。並且加入嚴格的「量體流動性濾網」剔除冷門股，最後套用頂尖分析師的選股邏輯來產出推薦。

## 任務 1: 實作財報與基本面爬蟲
- **檔案**: 建立 `scripts/fetch_financial_statements.py`
- **邏輯**:
  1. 使用 `requests` 從 `FinMind` API (或公開資訊觀測站) 取得上市櫃公司最新季報資料 (EPS, 稅後淨利, 合約負債)。
  2. 計算每個股的盈餘成長 (YoY / QoQ)，標記 `turnaround` (由虧轉盈)、`high_growth` (大幅成長)、`high_contract_liability` (高合約負債)。
  3. 將結果存入 `data/processed/fundamentals_latest.parquet`。

## 任務 2: 實作社群情緒與總經爬蟲
- **檔案**: 建立 `scripts/fetch_sentiment_and_macro.py`
- **邏輯**:
  1. 取得國內外重要大盤指數 (如 Nasdaq, S&P 500, 美元指數) 作為市場環境濾網。
  2. 爬取 PTT 股版或 Yahoo 新聞標題，進行簡單的正負面情緒判定，並統計提到特定股票的熱度。
  3. 存入 `data/processed/sentiment_latest.parquet`。

## 任務 3: 重構推薦模型 (核心大腦)
- **檔案**: `scripts/build_formal_json_outputs.py`
- **邏輯**:
  1. **流動性濾網**: 讀取 `daily_price.parquet`，將 20日均量 (`Vol_20d`) < 1000 張的股票一律從推薦清單剔除！
  2. 載入 `fundamentals_latest.parquet` 與 `sentiment_latest.parquet`。
  3. 計算一個新的綜合評分 `Alpha_Score_v5`，這要包含:
     - 籌碼面: 1/5/20日主力與法人買超強度。
     - 基本面: EPS 大幅成長、由黑翻紅加分。
     - 情緒面: 社群情緒分數。
     - 型態面: 套用 Mark Minervini 的 VCP 概念 (收斂後突破，即均線糾結後放量上漲)。
  4. 每種產業板塊最多只選出 3 檔綜合評分最高且通過流動性濾網的股票寫入 `recommendations_latest.json`。每檔標題需加上 `tags` 屬性 (例如 `["由虧轉盈", "情緒過熱", "法人連買"]`)。

## 任務 4: 前端顯示新因子標籤
- **檔案**: `web/src/App.tsx` 等相關組件
- **邏輯**:
  1. 讀取 `recommendations_latest` JSON 時，將股票旁邊加上這些彩色 `tags` (例如用綠色標記 `[由黑翻紅]`)。
  2. 確保在 `StockRadar` 或是相關選股介面中，能看到大師綜合評分與情緒溫度。

## 任務 5: 加入排程
- **檔案**: `scripts/run_daily_update.sh`
- **邏輯**: 在呼叫 `build_formal_json_outputs.py` 前，依序先執行 `fetch_financial_statements.py` 與 `fetch_sentiment_and_macro.py`。
