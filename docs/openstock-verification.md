# OpenStock 整合驗證 — 2026-09-18

## 通過

- `cd web && npm run build`：TypeScript 與 Vite production build 通過。
- `npm run test:openstock`：9 項 Node 模型測試全部通過，使用既有 2,320 筆 lookup 真實檔案。
- `npm run test:openstock-ui`：以 Chromium / Playwright 實際操作頁面並通過下列流程。
  - 台股資料載入、個股日期、過期價格提示，尚未按載入時不請求 TradingView。
  - 新增／移除自選，與原有自選監控共用，清空後重新整理不再自動填回。
  - Ctrl+K、00878 ETF 前導零、查無標的、沒有歷史走勢檔案的提示。
  - 主動模擬 TradingView 腳本網路失敗，驗證錯誤提示、重試、四種工具切換及卸載清理。
  - 390、768、1024、1440px 畫面有內容、無水平溢出。
  - 返回原本個股雷達正常；無 uncaught browser errors 或 Vite error overlay。
- `git diff --check` 通過。

## 實際界線

- 外部行情內容位於第三方 iframe；本次驗證了配置與失敗路徑，未證明每個台股 symbol 在 TradingView 都能取得報價／財務資料。
- Chromium 官方下載端遇到 502；改用暫存安裝的 `@sparticuz/chromium` 執行 Playwright。瀏覽器工具不加入產品依賴。
- 測試環境未安裝中文字體，截圖中的中文字形不可作為字體排版驗收證據；DOM 繁體文字與互動斷言通過。
- 原本首頁主 bundle 仍有 >500KB 的 Vite 提示；新增研究室為獨立 lazy chunk，約 10.74KB JS / 4.57KB CSS（未 gzip）。
- 未修復／驗證既有資料更新排程，未修改既有 `localhost:3000` 後端接口，未執行正式雲端部署。
- 本次不是完整 OpenStock 後端移植；帳號同步、通知、郵件、AI 摘要未接入。
