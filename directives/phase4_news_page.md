# Phase 4: 全球財經新聞獨立版面指南

## 目標
使用者不想要原本在上方的橫式跑馬燈，要求將全球財經動態獨立成左側 Sidebar 的一個新選單頁面，並且改用卡片或網格的方式呈現。

## 任務 1: 從首頁移除跑馬燈
- **檔案**: `web/src/App.tsx`
- **邏輯**: 將 `GlobalNewsTicker` 的相關程式碼與 `import` 移除。在 `App` 函數內回傳的 JSX 結構中，把 `<GlobalNewsTicker news={globalNews} />` 拿掉。但保留取得 `globalNews` 的 `fetch` 邏輯，並將其傳遞給新頁面。

## 任務 2: 新增側邊欄選單
- **檔案**: `web/src/App.tsx`
- **邏輯**: 在 `MENU` 陣列中新增一個項目：
  `{ key: "news", label: "全球財經", desc: "各國重點財經新聞" }`
  確保側邊欄點擊後可以將 `active` state 設為 `"news"`。

## 任務 3: 實作 GlobalNewsPage 元件
- **檔案**: `web/src/App.tsx` (或建立新的 `GlobalNewsPage.tsx`)
- **邏輯**:
  1. 建立 `function GlobalNewsPage({ news }: { news: GlobalNews[] })` 元件。
  2. 在 `PageRouter` 中，當 `active === "news"` 時渲染 `<GlobalNewsPage news={globalNews} />`。
  3. `GlobalNewsPage` 的內部設計：
     - 最外層給定 `className="panel"` 或是乾淨的 `flex column` 容器。
     - 包含一個大標題 `<h2>🌍 全球重點財經動態</h2>`。
     - 新聞列表使用 CSS Grid 呈現 (例如 `grid-template-columns: repeat(auto-fill, minmax(300px, 1fr))`)，讓每一則新聞變成一個獨立的漂亮卡片。
     - 每張新聞卡片包含標題、發布時間。點擊整張卡片可以直接以新分頁開啟原連結 (`target="_blank"`), hover 效果要明顯。

## 任務 4: 測試建置
- 執行 `cd web && npm run build` 確保編譯沒有問題，並符合 TypeScript 的型別定義。
