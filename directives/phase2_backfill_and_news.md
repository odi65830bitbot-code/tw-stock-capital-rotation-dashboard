# Phase 2: 回填歷史資料與全球財經動態實作指南

## 目標
1. 利用已有的 `finmind` 歷史資料，回填 `daily_price.parquet` 與 `institutional_flow.parquet`，以修復 5日/20日 資金流沒有變化的問題。
2. 實作 Google News RSS 爬蟲抓取財經新聞，並顯示在前端 Dashboard。

## 任務 1: 實作 backfill 腳本
- **檔案**: 建立 `scripts/backfill_from_finmind.py`
- **邏輯**:
  1. 讀取 `data/processed/finmind_price.parquet` 與 `data/processed/finmind_institutional.parquet`。
  2. 將 `finmind_price` 的 `stock_id` 改為 `stock_code`，過濾 4 位數普通股 (`^\d{4}$`)，確保包含 `trade_date, market, stock_code, close, change` (如果缺少則補上或計算)。
  3. 將 `finmind_institutional` 的 `stock_id` 改為 `stock_code`。它包含 `foreign_net_shares`, `trustee_net_shares`, `dealer_net_shares`。請計算 `three_party_net_shares` = 三者加總。
  4. 讀取現有的 `data/processed/daily_price.parquet` 與 `data/processed/institutional_flow.parquet`，使用 Pandas `concat` 與 `drop_duplicates(subset=['trade_date', 'stock_code'], keep='last')` 進行合併。
  5. 寫回 `data/processed/daily_price.parquet` 與 `data/processed/institutional_flow.parquet`。

## 任務 2: 執行 backfill 與重構 JSON
- **指令**: 
  - 在 CLI 內請呼叫 `python3 scripts/backfill_from_finmind.py` 進行回填。
  - 接著呼叫 `python3 scripts/build_formal_json_outputs.py` 重建所有正式的 JSON (這樣長天期資料就會被計算出來了)。

## 任務 3: 實作財經新聞爬蟲
- **檔案**: 建立 `scripts/fetch_global_news.py`
- **邏輯**:
  1. 使用 `requests` 與 `xml.etree.ElementTree`。
  2. 抓取 `https://news.google.com/rss/search?q=%E8%B2%A1%E7%B6%93+when:1d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant`。
  3. 解析 XML `<item>` 標籤，取出前 15 則新聞的 `title`, `link`, `pubDate`。
  4. 存入字典 `{"generated_at": "...", "records": [{"title": "...", "link": "...", "pubDate": "..."}]}`。
  5. 寫出至 `public/data/global_news_latest.json`。

## 任務 4: 加入每日排程
- **檔案**: 修改 `scripts/run_daily_update.sh`
- **邏輯**: 在呼叫 `update_daily.py` 的後面，加上一行 `"$PYTHON_BIN" "$ROOT/scripts/fetch_global_news.py"`。

## 任務 5: 前端 Dashboard 顯示
- **檔案**: 修改 `web/src/App.tsx` (或者如果系統是 `StandardDashboard.tsx` 則修改它)
- **邏輯**:
  1. 定義 `GlobalNews` 介面。
  2. 在 `useEffect` 中發送 `fetch('/data/global_news_latest.json')` 取得新聞。
  3. 在儀表板最頂端（Header 下方）加入一個跑馬燈 (Marquee) 或是水平捲動的 `<div className="flex overflow-x-auto ...">`，顯示「🌍 財經動態: [新聞標題 1] | [新聞標題 2] ...」。點擊新聞標題可以 `target="_blank"` 打開連結。請確保畫面美觀。
