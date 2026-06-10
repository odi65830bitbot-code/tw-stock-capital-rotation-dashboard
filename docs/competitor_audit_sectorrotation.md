# sectorrotation.netlify.app 競品稽核

## 摘要

本文件紀錄對 `https://sectorrotation.netlify.app/#` 的公開功能稽核。此稽核只基於公開網頁與公開 JSON，不直接複製對方程式碼。

目前可確認該站使用靜態 JSON 作為主要資料入口：

```text
https://sectorrotation.netlify.app/data/latest.json
```

截至本次檢查，該 JSON 的資料日期為 `2026-06-09`，包含：

- `sectors`：板塊清單與 1 日、5 日、20 日買賣超金額。
- `stock_data`：成分股層級的 1 日漲跌幅與 1 日買賣超金額。
- `market_chg_1d`：大盤 1 日漲跌幅。
- `updated_at`：資料產生時間。

## 可確認功能

### 靜態資料入口

前端會讀取 `data/latest.json`，再用資料欄位渲染首頁板塊輪動圖與排行榜。

可確認欄位：

- `date`
- `updated_at`
- `market_chg_1d`
- `is_market_down`
- `sectors`
- `stock_data`

### 板塊資料結構

每個板塊包含：

- `name`：板塊名稱，例如 `銀行金融`。
- `stocks`：板塊成分股代號。
- `net_1d_yi`：1 日買賣超金額，單位為億元。
- `net_5d_yi`：5 日買賣超金額，單位為億元。
- `net_20d_yi`：20 日買賣超金額，單位為億元。
- `position`：位置分數。
- `chg_1d`：板塊 1 日漲跌幅。
- `chg_5d`：板塊 5 日漲跌幅。
- `is_bottom_fishing`：是否符合抄底偵測。
- `bottom_score`：抄底分數。

### 成分股資料結構

`stock_data` 以股票代號為 key，值包含：

- `chg_1d`：個股 1 日漲跌幅。
- `net_1d_yi`：個股 1 日買賣超金額，單位為億元。

### 2026-06-09 觀察結果

本次公開資料顯示：

```text
第一名：銀行金融
1 日買賣超：113.16 億
5 日買賣超：257.53 億
20 日買賣超：378.12 億
1 日漲跌幅：4.82%
5 日漲跌幅：7.22%
成分股數：19
```

`銀行金融` 成分股包含：

```text
2881, 2882, 2891, 2880, 2884, 2885, 2886, 2887, 2890, 2892,
2883, 2888, 2889, 2801, 2809, 2812, 2823, 5876, 5880
```

## 不可從公開資料確認的部分

以下項目無法只從公開 JSON 完整確認：

- 是否使用完整 TWSE/TPEX 官方歷史資料重算 5 日與 20 日。
- 是否有後端排程或人工更新流程。
- `position` 的完整公式。
- `bottom_score` 的完整公式。
- 是否有會員功能、權限控管或後台資料修正。
- 是否有回測驗證。
- 是否處理資料失敗時的降級策略。

## 本專案升級方向

本專案不能直接複製該站程式碼，應採取以下策略：

- 官方 TWSE/TPEX 作為主資料源。
- FinMind 作為歷史與基本面補強。
- MoneyDJ、Yahoo、WantGoo 僅作交叉驗證與補充，不當核心資料源。
- 前端正式版改為 React + TypeScript。
- Streamlit 保留為研究版，不作正式產品前端。
- 所有資料輸出都需有日期、來源、欄位單位與品質狀態。

## 對照站欄位與本專案欄位對應

| 對照站欄位 | 本專案建議欄位 | 單位 | 說明 |
|---|---|---:|---|
| `name` | `sector_name` | 文字 | 板塊名稱 |
| `stocks` | `constituents` | 股票代號陣列 | 板塊成分股 |
| `net_1d_yi` | `net_1d_yi` | 億元 | 1 日法人買賣超金額 |
| `net_5d_yi` | `net_5d_yi` | 億元 | 5 日法人買賣超金額 |
| `net_20d_yi` | `net_20d_yi` | 億元 | 20 日法人買賣超金額 |
| `position` | `position_score` | 分數 | 板塊位置 |
| `chg_1d` | `sector_chg_1d_pct` | % | 板塊 1 日漲跌幅 |
| `chg_5d` | `sector_chg_5d_pct` | % | 板塊 5 日漲跌幅 |
| `is_bottom_fishing` | `is_bottom_fishing` | boolean | 抄底偵測 |
| `bottom_score` | `bottom_score` | 分數 | 抄底分數 |

## 風險

- 對照站板塊分類是主題式分類，不等同 TWSE 官方產業分類。
- 對照站使用買賣超金額，本專案原本部分資料使用買賣超股數，兩者不可混用排序。
- 若 TWSE/TPEX 當日價格或法人資料延遲，前端必須明確顯示資料日期與降級狀態。

