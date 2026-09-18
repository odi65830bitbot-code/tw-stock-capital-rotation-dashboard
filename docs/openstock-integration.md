# OpenStock 台股整合

## 目標與範圍

在既有 React 19 / Vite 台股儀表板導入 OpenStock 的 TradingView 元件，新增「OpenStock 研究室」。保留原本 Python 資料管線、輪動、Alpha、ETF、持股及個股雷達，無需新增 API 金鑰或遷移 Next.js。

已接入：台股與 ETF 搜尋、Ctrl/Cmd+K 聚焦搜尋、按代號或漲跌幅排序、原有自選清單、K 線／技術摘要／財務／公司介紹工具、既有歷史走勢備援、返回 Alpha／籌碼頁面。

這是功能移植，不是整套 OpenStock 部署。未接入 Better Auth、MongoDB、Finnhub、Inngest、AI 摘要、價格通知或自動郵件。這些功能需要另外配置服務及認證；介面不宣稱它們已可用。原有「警示設定」功能未在此次實作。

## Visual brief

- 使用目的：從盤後清單快速研究個股，回到原有 Alpha 與籌碼判讀。
- 使用者：馬克本人，手機與電腦均可操作。
- 主要 CTA：搜尋並選取股票；次要 CTA：加入自選、開啟外部圖表、查看 Alpha。
- 排版參考：OpenStock 搜尋 → 個股研究的資訊層級；造型參考：原專案側欄與雙欄清單；色彩／字體參考：原專案 styles.css 的暖白、墨綠與繁體中文字體。
- 色彩：暖白 #f6f5f0、墨綠 #2d7f73、陶橘 #c66a1b；台股紅漲綠跌。
- 字體：沿用 Avenir Next / PingFang TC / Noto Sans TC / system-ui。
- 禁止：新增大圓角 SaaS 三欄卡、藍紫漸層、發光球、未驗證即時行情或捏造資料。
- 手機：搜尋清單在上方、研究內容在下方；外部腳本僅於使用者載入時啟動；支援 reduced motion。

## 資料流

1. 原 App 讀取 `/data/stock_lookup_latest.json`，研究室共用該份資料，不再抓另一份全市場清單。
2. `model.ts` 保留字串代號與 ETF 前導零，只用明確 TWSE／TPEX 市場產生 TradingView symbol。
3. 個股 `price_date` 用於資料日期及老舊提示，不以整批生成日期替代。
4. 僅選取的股票讀取 `/data/trends/{code}.json`；檔案不存在、HTML fallback、代號不符及無有效價格皆顯示 unavailable，不合成假走勢。
5. TradingView 為另一來源，只補充展示，不回寫官方資料或 Alpha 計算。框架載入不等於行情可用，來源／時間不同會明示。
6. 共用 `tw_stock_watchlist`，按完整代號去重；保留使用者清空清單的選擇。localStorage 不提供跨裝置同步，寫入失敗有提示。

## 啟動與測試

```bash
cd web
npm ci
npm run test:openstock
npm run build
npm run dev
```

瀏覽器開啟 `http://127.0.0.1:5173/openstock`。可加 `?symbol=00878` 指定初始標的。

模型測試使用 Node 22.18+ / Node 24 的 TypeScript stripping；建置依既有專案環境。

瀏覽器 BDD 驗證腳本：`npm run test:openstock-ui`，需可用的 Playwright 與 Chromium；腳本自動啟動測試伺服器 `http://127.0.0.1:5187` 並在完成後關閉，也可以 `BASE_URL` 指向現有伺服器。腳本使用真實 repository JSON；僅模擬外部圖表網路失敗，以驗證 fallback，沒有編造行情。

## 部署與限制

- 既有 Vite 建置會攜帶 `public/data`、授權文件與新增分頁。靜態主機需提供 SPA fallback 以支援 `/openstock`。
- 這次沒有部署正式網站，也沒有合併 main。整合分支供檢查後合併。
- 現有後端 API 仍有 `localhost:3000` 依賴；此次研究室使用靜態 JSON，並未將整個網站的持股寫入／手動更新功能改成雲端服務。
- 截至導入時，lookup 批次日期為 2026-07-01；此次不宣稱恢復自動更新，亦未核實每筆上游行情正確性。
- TradingView 可能被封鎖、延遲或無該標的資料，隨時可關閉並看既有資料；iframe 內資料不由本網站驗證。
- AGPL 原文、作者與修改說明見根目錄 `THIRD_PARTY_NOTICES.md`；頁尾提供本版本完整程式庫連結。
- AGENTS.md 指定的 7 份 `/Users/maxyu/AI-Workspace/_shared/ai-context/` 全域文件在本次環境不存在：GLOBAL_AI_COLLAB_RULES.md、GLOBAL_PROJECT_MAP.md、GLOBAL_API_AUTH_INDEX.md、GLOBAL_ENV_INDEX.md、GLOBAL_OAUTH_FLOW_INDEX.md、GLOBAL_MCP_INDEX.md、GLOBAL_OBSIDIAN_RULES.md。後續接帳號或 API 前應補齊或同步這些索引；此次未假設其內容。
