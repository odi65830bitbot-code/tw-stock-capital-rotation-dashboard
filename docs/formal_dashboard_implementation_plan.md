# 台股資金輪動正式 Dashboard 實作計畫

## 目標

建立一個正式產品級的台股資金輪動互動網站，功能參考 `sectorrotation.netlify.app`，但資料底層以 TWSE/TPEX 官方資料為主，FinMind 為補強，並加入 CP 值、抄底偵測、Alpha v4、個股趨勢與回測。

## 不變原則

- 不直接複製競品程式碼。
- 不把 API token 寫進程式碼或前端。
- 不使用「必買」、「必漲」、「內線」等投資承諾字眼。
- 所有標的稱為「觀察標的」或「Alpha 候選股」。
- Streamlit 只保留為研究版，不作正式前端。
- 正式前端使用 React + TypeScript。

## Phase 0：保護現有成果

### 目標

先保留現有可運作的 Streamlit Dashboard 與每日資料更新，不直接破壞既有功能。

### 任務

- 建立 `docs/competitor_audit_sectorrotation.md`。
- 建立正式前端與資料管線遷移計畫。
- 保留目前 `src/dashboard/app.py` 作為研究版。
- 後續再將 Streamlit 移至 `legacy_streamlit/`。

### 完成狀態

- `docs/competitor_audit_sectorrotation.md` 已建立。
- `docs/formal_dashboard_implementation_plan.md` 已建立。

## Phase 1：正式資料輸出層

### 目標

在不重寫整個資料管線的前提下，先產生正式前端所需 JSON。

### 輸出檔案

```text
public/data/sector_rotation_latest.json
public/data/cp_ranking_latest.json
public/data/bottom_fishing_latest.json
public/data/sector_divergence_latest.json
public/data/stock_alpha_v4_latest.json
public/data/recommendations_v4_latest.json
public/data/trends/{stock_id}.json
```

### 模型

- `sector_rotation_model.py`
- `cp_value_model.py`
- `bottom_fishing_model.py`
- `sector_divergence_model.py`
- `stock_alpha_v4.py`
- `backtester_v4.py`
- `trend_builder_v4.py`

### 驗證

- 每份 JSON 都需含 `as_of_date`、`generated_at`、`source_status`。
- 至少用一個具名板塊與一個具名股票比對。
- `net_*_yi` 必須用金額，不可混用股數。

## Phase 2：React + TypeScript 正式前端

### 技術選型

建議使用 Vite + React + TypeScript。

原因：

- 現有專案不是 Next.js。
- 資料輸出為靜態 JSON，Vite 足夠。
- 部署到 Netlify/Vercel/GitHub Pages 都容易。
- 避免一開始引入 SSR 複雜度。

### 目錄

```text
web/
  src/
    app/
    components/
    lib/
    types/
  public/
    data/
  package.json
  vite.config.ts
```

### 首頁區塊

- 市場總覽。
- 板塊輪動泡泡圖。
- CP 值排行。
- 抄底偵測。
- 今日觀察標的 Top 10。
- 回測摘要。

### 視覺方向

- 深墨色金融看板。
- 單一主色使用資金綠。
- 卡片式資訊，但避免過度工程師感。
- 手機版優先保留首頁總覽、板塊排行與搜尋。

## Phase 3：頁面路由

### 頁面

```text
/
/sectors
/sector/:sectorId
/stocks
/stock/:stockId
/recommendations
/backtest
```

### 核心互動

- 泡泡點擊後顯示板塊詳情。
- 板塊頁可依 1D、5D、20D、Alpha 排序。
- 個股頁顯示價格、成交值、法人、Alpha、營收與財報趨勢。
- 推薦頁以「觀察理由」而非投資建議呈現。

## Phase 4：回測與品質

### 回測

- Sector Alpha。
- CP 模型。
- 抄底模型。
- Stock Alpha v4。
- 對照加權指數與 0050。

### 品質

- 資料來源缺失時顯示降級狀態。
- 當日資料未齊時沿用上一交易日，不讓前端崩潰。
- 金額與股數欄位明確分開。
- 每次更新產出品質報告。

## Phase 5：自動化與部署

### 每日更新

- 本機 macOS LaunchAgent 保留。
- GitHub Actions 增加每日排程。
- 每日更新後產出 public JSON。

### 部署

- 正式前端部署到 Vercel 或 Netlify。
- Streamlit 僅保留本機研究用途。

## 下一步建議

下一步應先做 Phase 1，原因是正式前端需要穩定 JSON 契約。如果先做 React UI，後面資料欄位會一直變，會造成返工。

建議第一個實作任務：

```text
建立 data_pipeline/models/sector_rotation_model.py
產生 public/data/sector_rotation_latest.json
欄位包含 net_1d_yi、net_5d_yi、net_20d_yi、accel、position_score、chg_1d、chg_5d、category
```

