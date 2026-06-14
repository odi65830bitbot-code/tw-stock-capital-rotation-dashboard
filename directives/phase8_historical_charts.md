# Phase 8: 板塊輪動區新增三種歷史資金視覺化圖表

## 目標
在現有的板塊輪動區塊（目前是 Treemap）上方加入 Tab 切換器，讓使用者可以在四種視圖之間切換：
1. **板塊圖** (Treemap) — 現有的，保持不動
2. **資金河流** (Stream/Stacked Area Chart) — 新增
3. **資金熱力** (Heatmap Grid) — 新增
4. **法人流向** (Sankey Diagram) — 新增

## 前置：資料管線

### 任務 1: 在 `build_formal_json_outputs.py` 新增 `sector_flow_history.json`
- 從 `institutional_flow.parquet` 讀取個股法人買賣超
- 與 `sector_classification.parquet` 做 join，取得每檔股票的 `industry` 板塊標籤
- 按 `(trade_date, industry)` 聚合，計算每日每板塊的：
  - `foreign`: 外資淨買賣超張數合計
  - `trust`: 投信淨買賣超張數合計
  - `dealer`: 自營商淨買賣超張數合計
  - `total`: 三方合計
- 只保留最近 60 個交易日的資料（河流圖用 20 天、熱力圖用 20 天、桑基圖可選不同時間範圍）
- 輸出格式：
```json
{
  "generated_at": "...",
  "as_of_date": "2026-06-11",
  "dates": ["2026-04-01", "2026-04-02", ...],
  "sectors": ["半導體業", "金融保險業", ...],
  "data": [
    { "date": "2026-04-01", "sector": "半導體業", "foreign": 12345, "trust": 6789, "dealer": -1234, "total": 17900 },
    ...
  ]
}
```
- 在 `main()` 中呼叫此函式並寫入 `public/data/sector_flow_history.json`
- 在 `run_daily_update.sh` 的流程中不需額外加步驟，因為 `build_formal_json_outputs.py` 本身就在排程裡

### 任務 2: 確認 `sector_flow_history.json` 正確產出
- 執行 `python3 scripts/build_formal_json_outputs.py`
- 確認 `public/data/sector_flow_history.json` 存在且有資料

## 前端實作

### 任務 3: 安裝圖表依賴
- 在 `web/` 目錄下執行 `npm install recharts` (用於河流圖/面積圖)
- 桑基圖和熱力圖用純 SVG/CSS 手刻即可，不需額外套件

### 任務 4: 新增 Tab 切換 UI
- 在 `App.tsx` 中，找到板塊輪動的 `<section>` 區塊
- 在該區塊內部、圖表上方加入四個 Tab 按鈕：「板塊圖」「資金河流」「資金熱力」「法人流向」
- 使用 `useState` 控制目前顯示哪個 Tab，預設為「板塊圖」
- Tab 按鈕樣式套用現有的 `.tabs` CSS class
- 點擊 Tab 時切換顯示對應的圖表元件，其他三個隱藏

### 任務 5: 實作「資金河流圖」(StreamChart)
- 使用 Recharts 的 `<AreaChart>` + `<Area>` (stacked)
- 從 `sector_flow_history.json` 讀取數據，取最近 20 天
- X 軸 = trade_date，Y 軸 = 每日各板塊的 total（三方合計）
- 只顯示資金流入量最大的 Top 8 板塊（避免太擁擠）
- 每個板塊用不同的漸層色填充
- 暗色主題：背景透明，軸線用 var(--muted)，文字用 var(--text)
- 圖表高度約 400px，響應式寬度

### 任務 6: 實作「資金熱力圖」(HeatmapGrid)
- 使用純 CSS Grid + 動態背景色
- 從 `sector_flow_history.json` 讀取數據，取最近 20 天
- 行 = 各板塊（按當日 total 排序），列 = 20 個交易日
- 每格的背景色：深綠 = 大量買入、淡綠 = 小量買入、灰 = 中性、淡紅 = 小量賣出、深紅 = 大量賣出
- 顏色映射：根據該板塊的 total 值，用線性插值映射到 hsl 色相（紅~綠）
- Hover 時顯示 tooltip：「板塊名 日期: +XX 張」
- 圖表高度自適應，左側標籤固定寬度

### 任務 7: 實作「法人流向桑基圖」(SankeyChart)
- 使用純 SVG 手刻（或使用簡單的 path 繪製）
- 左側三個節點：外資、投信、自營商
- 右側節點：Top 10 板塊（按淨買超金額排序）
- 流量（ribbon）的粗細 = 該法人對該板塊的淨買超絕對值
- 顏色：買入 = 綠色系 ribbon，賣出 = 紅色系 ribbon
- 上方加入時間選擇器：「今日」「本週」「本月」三個按鈕
  - 今日 = 只看最近 1 天
  - 本週 = 最近 5 天的加總
  - 本月 = 最近 20 天的加總
- 圖表高度約 450px

### 任務 8: 樣式與動畫
- Tab 切換時加入淡入淡出 transition（opacity 0→1, 0.3s ease）
- 河流圖的面積有漸層透明效果
- 熱力圖每格有 hover 時微微放大的效果（transform: scale(1.3)）
- 桑基圖的 ribbon hover 時高亮（opacity 提高）
- 所有新元件遵循現有的 dark theme 色彩系統

### 任務 9: 測試
- 確認 `npm run build` 通過
- 確認四個 Tab 都能正常切換
- 確認每個圖表都有數據呈現（不是空白）
