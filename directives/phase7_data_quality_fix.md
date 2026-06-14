# Phase 7: 數據品質優化與 NA 空值填補

## 背景
根據 `verify_data_quality.py` 的檢查報告，目前 JSON 輸出管線有多項 `null` 值警告。
主要原因是：
1. 法人 (外資/投信/自營商) 買賣超在無交易的股票上會呈現空值，而非 `0`。
2. 某些股票當日可能停牌或無成交，導致 `close` 或 `change_pct` 為空值。
3. `market_latest.json` 中某些指數 (如 TPEx50Index) 缺乏當日漲跌幅資料。

## 任務 1: 修改 JSON 產出邏輯填補 NA
**檔案**: `scripts/build_formal_json_outputs.py`

在產出各種 `_latest.json` 時，對 Pandas DataFrame 進行 `fillna`：
1. **買賣超填補**: 針對 `foreign_net_shares`, `trustee_net_shares`, `dealer_net_shares`, `foreign_net_yi`, `trust_net_yi`, `dealer_net_yi` 等法人籌碼欄位，全面使用 `.fillna(0)` 補 0。
2. **價格與漲跌幅填補**: 針對 `close`, `change`, `change_pct`，如果是個股無資料，請考慮用 `.fillna(0)` 填補 `change` 與 `change_pct`，`close` 則保留或以特殊方式處理（若 `verify_data_quality.py` 需要）。
3. **大盤指數填補**: 在 `build_market_summary` 中，如果 TPEx50Index 等指數的 `change_pct` 缺漏，請用 `.fillna(0)` 補為 0。
4. **推薦清單**: 在 `build_recommendations` 時，也記得處理 `foreign_net_shares` 補 0。

## 任務 2: 驗證
1. 執行 `python3 scripts/build_formal_json_outputs.py`。
2. 執行 `python3 scripts/verify_data_quality.py`，確保之前的 3 個黃燈警告全部消失，顯示「完全符合標準」。
