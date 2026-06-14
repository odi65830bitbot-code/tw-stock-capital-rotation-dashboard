# Phase 6: 解除全市場個股趨勢檔案 (trends JSON) 的預建限制

## 目標
目前 `trends` 資料夾內的 JSON 檔案，因為效能考量，每日盤後僅產生「今日推薦 Top 10」的個股。這導致使用者若在搜尋框輸入非 Top 10 的冷門股或特定標的（如 `8358`）時，前端會拋出「趨勢資料未收錄」的錯誤。我們需要解除這個限制，讓全市場約 1800 檔個股都能擁有自己的專屬趨勢檔案。

## 任務 1: 修改後端參數
- **檔案**: `scripts/update_daily.py` 與 `scripts/update_finmind_data.py`
- **邏輯**: 尋找呼叫 `write_top_recommendation_trends` 或 `write_finmind_recommendation_trends` 的地方，將參數 `top_n=10` 改為 `top_n=2000` (或直接移除該參數如果模組層已有處理)。
- **檔案**: `src/modules/trend_builder.py` 與 `src/modules/trend_builder_finmind.py` (若有)
- **邏輯**: 將 `top_n` 參數的預設值改為 `2000`。

## 任務 2: 移除前端錯誤提示
- **檔案**: `web/src/App.tsx` (或包含該錯誤提示的元件)
- **邏輯**: 找到 `為保障資料管線效能，系統每日盤後僅預建當日評級最優之 Top 10 觀察股趨勢...` 這段警語，將其從畫面上完全移除，避免對使用者產生誤導。保留如果檔案真的找不到時的通用錯誤訊息即可（例如：「找不到該股票代號的趨勢檔案」）。

## 任務 3: 重建所有 JSON 並測試
- **指令**: 在 CLI 中執行 `python3 scripts/update_daily.py` 或是特定的更新腳本，確保 `public/data/trends/` 資料夾中產生了大量（>1000個）的 JSON 檔案，包含 `8358.json`。
- **測試**: 確認 `npm run build` 通過。
