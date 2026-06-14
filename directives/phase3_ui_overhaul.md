# Phase 3: 板塊圖與介面全面優化指南

## 目標
1. 在所有個股清單中，補齊「股票名稱」(如 `1736 喬山` 而非僅 `1736`)。
2. 將原本網頁上的「回測效能摘要」JSON 區塊移除。
3. 將「泡泡圖」升級改版為「可互動板塊圖 (Treemap)」，支援點擊放大，並顯示個股的 1/5/20日 資金流向與漲跌。

## 任務 1: 股票名稱顯示補齊
- **檔案**: 搜尋 `web/src` 下的元件 (特別是 `App.tsx` 或負責渲染清單的 Component)。
- **邏輯**: 尋找渲染 `stock_code` 的地方，將 `{row.stock_code}` 改為 `{row.stock_code} {row.stock_name}`。請注意保持版面排版，若過長請套用 CSS 截斷。

## 任務 2: 移除回測摘要 JSON
- **檔案**: `web/src/App.tsx` (或其他 Dashboard Component)
- **邏輯**: 尋找顯示 `backtest-v4-summary-formal-v1` 的 `<div className="panel">` 或 `<pre>` 區塊，直接將其從 JSX 渲染樹中移除。

## 任務 3: 泡泡圖替換為板塊圖 (Treemap)
- **檔案**: `web/src/App.tsx` (或建立新的 `SectorTreemap.tsx` 元件並引入)
- **邏輯**:
  1. 移除原本的 `BubbleChart` / `ScatterChart`。
  2. 使用 `recharts` 的 `Treemap` 或手刻 CSS Grid 方塊來建立板塊圖。
  3. **第一層視角 (巨觀)**：顯示各大產業板塊。方塊大小依據總資金或家數決定，顏色依據板塊的 `net_1d_yi` (或漲跌) 決定深淺。
  4. **第二層視角 (微觀)**：加入 `onClick` 事件，點擊板塊後，進入該板塊的詳細檢視模式。在此模式下，將該板塊下的所有成分股 (`sector_constituents_latest.json` 中的股票) 顯示為方塊。每個方塊內需呈現：
     - 個股代號與名稱 (`{stock_code} {stock_name}`)
     - 今日漲跌幅 (如 `+5.3%`)
     - 1日買賣超 (`net_1d_yi`)
     - 5日買賣超 (`net_5d_yi`)
     - 20日買賣超 (`net_20d_yi`)
  5. 請提供「返回全市場板塊」的按鈕。

## 任務 4: 前端樣式與建置檢查
- **邏輯**: 在 CLI 中執行 `cd web && npm run build` 確認 TypeScript 型別無誤且打包成功。確保畫面美觀且符合原系統（黑底綠色系）的風格。
