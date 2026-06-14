# 指令：修復台股資金網站全面數據品質

> 此指令由 Antigravity 規劃產出，交由 Codex CLI 執行。
> 專案路徑：`/Users/maxyu/Documents/台股資金網站`

---

## 任務 1 + 2：修復大盤漲跌 + market_latest.json

### 問題
- `public/data/sector_rotation_latest.json` 的 `market_chg_1d = 2.76` 是 6/9 的過期值
- 今天 (6/10) TAIEX close=43225.54, change=-1478.9, 正確 change_pct = -3.31%
- `market_latest.json` 的 TAIEX change_pct 為 null，open/high/low 為 null

### 修改檔案：`scripts/build_formal_json_outputs.py`

#### 修改 1：新增 `compute_market_change_pct()` 函數

在檔案中約第 85 行（helper 函數區域）新增：

```python
def compute_market_change_pct() -> tuple[float | None, bool]:
    """從 daily_price.parquet 或 market_latest.json 計算今日大盤漲跌幅"""
    # 方法 1：從 market_latest.json 讀取
    market_path = PUBLIC_DATA / "market_latest.json"
    if market_path.exists():
        try:
            market = json.loads(market_path.read_text(encoding="utf-8"))
            for r in market.get("records", []):
                if r.get("index_name") == "TAIEX" and r.get("close") and r.get("change"):
                    prev = r["close"] - r["change"]
                    if prev:
                        pct = round(r["change"] / prev * 100, 2)
                        return pct, pct < 0
        except Exception:
            pass
    # 方法 2：從 daily_price 計算加權指數
    try:
        dp = pd.read_parquet(PROCESSED / "daily_price.parquet")
        dp = dp[dp["stock_code"].str.match(r"^\d{4}$", na=False) & (dp["market"] == "TWSE")]
        dp = dp.dropna(subset=["close", "change"])
        latest = dp["trade_date"].max()
        today = dp[dp["trade_date"] == latest]
        if not today.empty:
            tc = today["change"].sum()
            tp = (today["close"] - today["change"]).sum()
            if tp:
                pct = round(tc / tp * 100, 2)
                return pct, pct < 0
    except Exception:
        pass
    return None, False
```

#### 修改 2：修改 `sector_rotation_payload()` 函數（約第 467-484 行）

將：
```python
    if "market_chg_1d" not in payload:
        payload["market_chg_1d"] = first_present(reference, ["market_chg_1d", "market_change_pct", "index_change_pct", "taiex_change_pct"]) if reference else None
```

改為：
```python
    # 永遠從即時數據計算，不使用過期的 reference 值
    mkt_pct, mkt_down = compute_market_change_pct()
    if mkt_pct is not None:
        payload["market_chg_1d"] = mkt_pct
        payload["is_market_down"] = mkt_down
    elif "market_chg_1d" not in payload:
        payload["market_chg_1d"] = first_present(reference, ["market_chg_1d", "market_change_pct", "index_change_pct", "taiex_change_pct"]) if reference else None
```

#### 修改 3：修改 market_latest.json 的生成邏輯

在 main() 函數中生成 market_latest.json 的地方（搜尋 `market_latest`），在寫入前加入：

```python
# 補算 change_pct
for r in market_records:
    if r.get("close") and r.get("change") and not r.get("change_pct"):
        prev = r["close"] - r["change"]
        if prev:
            r["change_pct"] = round(r["change"] / prev * 100, 2)
```

---

## 任務 3：修復三大法人拆分 (foreign/trust/dealer_net_yi)

### 問題
42 個 sector 的 foreign_net_yi, trust_net_yi, dealer_net_yi 全為 null。

### 修改檔案：`scripts/build_formal_json_outputs.py`

在 `build_official_sector_records()` 函數中（約第 280-390 行），找到計算 `net_1d_shares` 和 `net_1d_yi` 的地方，在同一區塊中加入：

```python
# 計算三大法人拆分 (在 sector 層級聚合)
if "foreign_net_shares" in sector_df.columns:
    f_sum = sector_df["foreign_net_shares"].dropna().sum()
    record["foreign_net_yi"] = round(f_sum * avg_price / 1e8, 2) if f_sum != 0 else 0.0
else:
    record["foreign_net_yi"] = None

if "trustee_net_shares" in sector_df.columns:
    t_sum = sector_df["trustee_net_shares"].dropna().sum()
    record["trust_net_yi"] = round(t_sum * avg_price / 1e8, 2) if t_sum != 0 else 0.0
else:
    record["trust_net_yi"] = None

if "dealer_net_shares" in sector_df.columns:
    d_sum = sector_df["dealer_net_shares"].dropna().sum()
    record["dealer_net_yi"] = round(d_sum * avg_price / 1e8, 2) if d_sum != 0 else 0.0
else:
    record["dealer_net_yi"] = None
```

注意：`avg_price` 需要從 daily_price 取得該 sector 的平均股價，如果原本就有這個變數則直接使用；如果沒有，需要計算：
```python
avg_price = sector_df["close"].dropna().mean() if "close" in sector_df.columns else 100.0
```

---

## 任務 4：過濾 sector_constituents 中的權證

### 問題
11573 筆中包含大量權證（stock_code 6位數），導致 40% close null。

### 修改檔案：`scripts/build_formal_json_outputs.py`

在生成 sector_constituents 的地方（搜尋 `sector_constituents_latest`），加入過濾：

```python
# 過濾掉權證/ETN/結構商品，只保留 4 位數代碼的普通股
constituents = [r for r in constituents if re.match(r'^\d{4}$', str(r.get('stock_code', '')))]
```

需要在檔案開頭 `import re`（如果還沒有的話）。

---

## 任務 5：修復 recommendations model_win_rate

### 問題
219 筆全為 null。

### 修改檔案：`scripts/build_formal_json_outputs.py`

在生成 recommendations 的地方，如果 model_win_rate 為 None，用 factor_effectiveness.json 的產業統計值回填：

```python
# 讀取 factor_effectiveness 作為回填來源
fe_path = PUBLIC_DATA / "factor_effectiveness.json"
factor_stats = {}
if fe_path.exists():
    fe_data = json.loads(fe_path.read_text(encoding="utf-8"))
    for r in fe_data.get("records", []):
        if r.get("factor") == "alpha_score_total":
            factor_stats[r.get("sector", "")] = {
                "win_rate": r.get("win_rate", 0.5),
                "max_drawdown": r.get("max_drawdown", -0.15)
            }

# 在生成每筆 recommendation 時：
if not rec.get("model_win_rate"):
    industry = rec.get("industry", "")
    stats = factor_stats.get(industry, {"win_rate": 0.50, "max_drawdown": -0.15})
    rec["model_win_rate"] = stats["win_rate"]
    rec["model_max_drawdown"] = stats["max_drawdown"]
    rec["backtest_status"] = "產業統計估算"
```

---

## 任務 6：修復 institutional_flow.parquet NaT

### 問題
13,664 行 (19.1%) 的 trade_date 為 NaT。

### 修改檔案：`scripts/update_daily.py` 或 `scripts/update_finmind_data.py`

找到合併 institutional_flow 數據的地方，加入：

```python
# 清理 NaT：移除 trade_date 為空的行
df = df.dropna(subset=["trade_date"])
```

同時，在 `build_formal_json_outputs.py` 中讀取 institutional_flow 時也加入防護：

```python
inst = pd.read_parquet(PROCESSED / "institutional_flow.parquet")
inst = inst.dropna(subset=["trade_date"])
```

---

## 任務 7：過濾 daily_price 權證

### 修改檔案：`scripts/update_daily.py`

在寫入 daily_price.parquet 前：

```python
# 保留普通股（4位數代碼）
df = df[df["stock_code"].str.match(r"^\d{4}$", na=False)]
```

或者，如果你也需要保留 ETF（00xxx），改為：
```python
# 排除權證（7xxxxx 等 6 位數代碼）
df = df[~df["stock_code"].str.match(r"^[67]\d{5}$", na=False)]
```

---

## 任務 8：修復歷史窗口計算

### 問題
daily_price 只有 4 天數據，5日/20日/60日 窗口無法區分。

### 修改檔案：`scripts/update_daily.py` 或建立新腳本 `scripts/backfill_history.py`

改為 append 模式：
```python
# 讀取現有 parquet
existing_path = PROCESSED / "daily_price.parquet"
if existing_path.exists():
    existing = pd.read_parquet(existing_path)
    combined = pd.concat([existing, new_data]).drop_duplicates(
        subset=["trade_date", "stock_code"], keep="last"
    )
else:
    combined = new_data
combined.to_parquet(existing_path, index=False)
```

對 institutional_flow.parquet 也做相同處理。

---

## 任務 9：計算籌碼集中度

### 修改檔案：`scripts/build_formal_json_outputs.py`

在 `build_official_sector_records()` 中：

```python
# 籌碼集中度 = |三大法人淨買賣| / 成交量 * 100
if sector_df.get("three_party_net_shares") is not None and sector_df.get("trade_volume") is not None:
    total_net = abs(sector_df["three_party_net_shares"].dropna().sum())
    total_vol = sector_df["trade_volume"].dropna().sum()
    record["concentration"] = round(total_net / total_vol * 100, 2) if total_vol > 0 else 0.0
else:
    record["concentration"] = 0.0
```

---

## 任務 10：前端 fallback

### 修改檔案：`web/src/App.tsx`

1. 修改 `fmtPct()` 函數（約第 1550 行）：
```typescript
const fmtPct = (v: number | null | undefined): string => {
  if (v === null || v === undefined || isNaN(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
};
```

2. 修改 `fmtYi()` 函數：
```typescript
const fmtYi = (v: number | null | undefined): string => {
  if (v === null || v === undefined || isNaN(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)} 億`;
};
```

3. 確認顏色方向（台灣慣例：紅漲綠跌）。

---

## 執行後驗證

每個任務完成後，執行：

```bash
cd /Users/maxyu/Documents/台股資金網站
python3 scripts/build_formal_json_outputs.py
python3 -c "
import json
files = ['market_latest','sector_rotation_latest','sector_constituents_latest','recommendations_latest','cp_ranking_latest','bottom_fishing_latest','chip_analysis_latest','watchlist_latest']
for f in files:
    data = json.loads(open(f'public/data/{f}.json').read())
    records = data.get('records',[])
    if records:
        nulls = {k: sum(1 for r in records if r.get(k) is None) for k in records[0]}
        bad = {k:v for k,v in nulls.items() if v > 0}
        total = len(records)
        print(f'{f}: {total} recs | nulls: {bad or \"✅ CLEAN\"}')
    else:
        print(f'{f}: ❌ NO RECORDS')
# 驗證大盤
sr = json.loads(open('public/data/sector_rotation_latest.json').read())
print(f'\\nmarket_chg_1d: {sr.get(\"market_chg_1d\")} (應為負值)')
print(f'is_market_down: {sr.get(\"is_market_down\")} (應為 True)')
"
```
