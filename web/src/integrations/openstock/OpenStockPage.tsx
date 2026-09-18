// SPDX-License-Identifier: AGPL-3.0-only
import { useEffect, useMemo, useRef, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import TradingViewWidget from "./TradingViewWidget";
import { normalizeStocks, priceAgeDays, searchStocks, tradingViewSymbol, validDate, watchCode, type WidgetKind } from "./model";
import "./openstock.css";

interface Props {
  lookup: Record<string, unknown> | null;
  lookupStatus: string;
  watchlist: string[];
  toggleWatch: (label: string) => void;
  onNavigateToStock: (code: string) => void;
}
const TABS: { key: WidgetKind; label: string }[] = [
  { key: "chart", label: "進階 K 線" }, { key: "technicals", label: "技術摘要" },
  { key: "financials", label: "財務資料" }, { key: "profile", label: "公司簡介" },
];
const format = (n: number | null) => n === null ? "—" : n.toLocaleString("zh-TW", { maximumFractionDigits: 2 });

export default function OpenStockPage({ lookup, lookupStatus, watchlist, toggleWatch, onNavigateToStock }: Props) {
  const stocks = useMemo(() => normalizeStocks(lookup), [lookup]);
  const byCode = useMemo(() => new Map(stocks.map(s => [s.code, s])), [stocks]);
  const [query, setQuery] = useState("");
  const [onlyWatched, setOnlyWatched] = useState(false);
  const [sort, setSort] = useState<"code" | "change">("code");
  const [selected, setSelected] = useState(() => new URLSearchParams(location.search).get("symbol") || "2330");
  const [kind, setKind] = useState<WidgetKind>("chart");
  const [externalEnabled, setExternalEnabled] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const searchRef = useRef<HTMLInputElement>(null);
  const watched = useMemo(() => new Set(watchlist.map(watchCode)), [watchlist]);
  const results = useMemo(() => {
    const filtered = searchStocks(stocks, query).filter(s => !onlyWatched || watched.has(s.code));
    return filtered.sort((a, b) => sort === "change"
      ? (b.changePct ?? -Infinity) - (a.changePct ?? -Infinity) || a.code.localeCompare(b.code)
      : Number(b.code === query.trim().toUpperCase()) - Number(a.code === query.trim().toUpperCase()) || a.code.localeCompare(b.code));
  }, [stocks, query, onlyWatched, watched, sort]);
  const stock = byCode.get(selected);
  const symbol = stock ? tradingViewSymbol(stock) : null;
  const age = stock ? priceAgeDays(stock.priceDate) : null;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault(); searchRef.current?.focus(); searchRef.current?.select();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return <section className="os-page" aria-label="OpenStock 研究室">
    <header className="os-heading">
      <div><p className="os-eyebrow">MARK’S ESCAPE PLAN · OPENSTOCK</p><h2>把市場看得更清楚。</h2>
        <p>搜尋台股與 ETF，從熟悉的清單展開研究。</p></div>
      <span className="os-batch">盤後觀察 · 非即時報價</span>
    </header>
    <div className="os-workspace">
      <aside className="os-panel os-search-panel">
        <label htmlFor="os-search">搜尋股票／ETF <kbd>⌘ / Ctrl K</kbd></label>
        <input id="os-search" ref={searchRef} type="search" value={query}
          placeholder="輸入代號、名稱或產業" onChange={e => setQuery(e.target.value)} />
        <div className="os-filters">
          <button type="button" aria-pressed={!onlyWatched} onClick={() => setOnlyWatched(false)}>全部</button>
          <button type="button" aria-pressed={onlyWatched} onClick={() => setOnlyWatched(true)}>我的自選 {watched.size}</button>
          <label className="os-sort">排序<select aria-label="股票排序" value={sort} onChange={e => setSort(e.target.value as "code" | "change")}>
            <option value="code">代號</option><option value="change">漲跌幅</option>
          </select></label>
        </div>
        <p className="os-caption" role="status">{lookupStatus === "loading" ? "正在讀取台股資料…" : lookupStatus !== "ready"
          ? "台股資料無法載入，請稍後重新整理。" : `找到 ${results.length} 檔${results.length > 80 ? "，顯示前 80 檔，請輸入關鍵字縮小範圍" : ""}`}</p>
        <div className="os-results">
          {results.slice(0, 80).map(item => <button type="button" key={item.code} aria-pressed={selected === item.code}
            className="os-result" onClick={() => setSelected(item.code)}>
            <span><strong>{item.name}</strong><small>{item.code} · {item.market}{watched.has(item.code) ? " · ★" : ""}</small></span>
            <span><strong>{format(item.close)}</strong><small className={item.changePct === null ? "" : item.changePct >= 0 ? "os-up" : "os-down"}>
              {item.changePct === null ? "漲跌缺值" : `${item.changePct > 0 ? "+" : ""}${format(item.changePct)}%`}</small></span>
          </button>)}
          {lookupStatus === "ready" && !results.length && <p className="os-empty">{onlyWatched ? "自選清單沒有符合的標的，切換「全部」搜尋並加入。" : "找不到符合的股票或 ETF，試試代號或部分名稱。"}</p>}
        </div>
        <p className="os-caption">自選清單共用原有「自選監控」，保存在此瀏覽器；手機與電腦尚未同步。</p>
      </aside>

      <div className="os-detail">
        {!stock ? <div className="os-panel os-empty">{lookupStatus === "loading" ? "正在讀取標的…" : "請從清單選擇一檔股票或 ETF。"}</div> : <>
          <section className="os-panel os-summary">
            <div><p className="os-eyebrow">{stock.market} / {stock.code} / {stock.industry}</p><h3>{stock.name}</h3>
              <div className="os-price"><strong>{format(stock.close)}</strong><span>TWD</span>
                <span className={stock.changePct === null ? "" : stock.changePct >= 0 ? "os-up" : "os-down"}>
                  {stock.changePct === null ? "漲跌缺值" : `${stock.changePct > 0 ? "+" : ""}${format(stock.changePct)}%`}</span></div>
            </div>
            <div className="os-actions">
              <button type="button" className="os-primary" aria-pressed={watched.has(stock.code)} onClick={() => toggleWatch(`${stock.code} ${stock.name}`)}>
                {watched.has(stock.code) ? "★ 移出自選" : "☆ 加入自選"}</button>
              <button type="button" onClick={() => onNavigateToStock(stock.code)}>查看台股 Alpha 與籌碼 →</button>
            </div>
            <p className="os-date">此標的價格日期：{stock.priceDate ?? "未提供"} · 來源：既有台股盤後資料管線</p>
            {(age === null || age < 0 || age > 7) && <p className="os-warning" role="status">{age === null ? "無法確認此標的價格日期，請先核對來源。" : age < 0 ? "價格日期晚於目前日期，請核對來源。" : `這筆價格距今 ${age} 個日曆日；資料尚未更新，請勿視為目前行情。`}</p>}
          </section>

          <section className="os-panel">
            <div className="os-tabs" aria-label="外部研究工具">
              {TABS.map(tab => <button type="button" key={tab.key} aria-pressed={kind === tab.key} onClick={() => setKind(tab.key)}>{tab.label}</button>)}
            </div>
            <p className="os-caption">TradingView 補充資料，可能延遲或不支援此標的；與上方盤後價格的時間及來源不同。</p>
            {!symbol ? <p className="os-empty">尚未確認此標的交易所，無法對應外部圖表。</p> : !externalEnabled ? <div className="os-connect">
              <strong>開啟更完整的市場視角</strong><p>K 線、技術摘要與公司資料由 TradingView 提供。</p>
              <button className="os-primary" type="button" onClick={() => setExternalEnabled(true)}>載入 TradingView 圖表</button>
            </div> : <>
              <TradingViewWidget key={`${symbol}-${kind}-${attempt}`} symbol={symbol} kind={kind} onRetry={() => setAttempt(v => v + 1)} />
              <button className="os-text-button" type="button" onClick={() => setExternalEnabled(false)}>關閉外部圖表</button>
            </>}
          </section>
          <LocalTrend key={stock.code} code={stock.code} />
        </>}
      </div>
    </div>
    <footer className="os-footer">
      <span>僅供觀察研究（observation-only），不構成買賣建議。</span>
      <span>整合自 <a href="https://github.com/Open-Dev-Society/OpenStock" target="_blank" rel="noopener noreferrer">Open Dev Society / OpenStock</a>
        {" · "}<a href="/licenses/OpenStock-AGPL-3.0.txt" target="_blank" rel="noopener noreferrer">AGPL-3.0</a>
        {" · "}<a href="https://github.com/odi65830bitbot-code/tw-stock-capital-rotation-dashboard/tree/feat/openstock-taiwan-integration" target="_blank" rel="noopener noreferrer">本版本原始碼</a></span>
    </footer>
  </section>;
}

function LocalTrend({ code }: { code: string }) {
  const [state, setState] = useState<{ status: string; points: { date: string; close: number }[] }>({ status: "loading", points: [] });
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/data/trends/${encodeURIComponent(code)}.json`, { signal: controller.signal })
      .then(async response => {
        if (!response.ok || response.headers.get("content-type")?.includes("text/html")) throw new Error("unavailable");
        const payload = await response.json();
        if (String(payload.stock_id) !== code) throw new Error("symbol mismatch");
        const price: unknown[] = Array.isArray(payload.price) ? payload.price : [];
        const points = price.flatMap(value => {
          if (!value || typeof value !== "object") return [];
          const row = value as Record<string, unknown>;
          const date = validDate(row.trade_date);
          return date && typeof row.close === "number" && Number.isFinite(row.close) && row.close > 0 ? [{ date, close: row.close }] : [];
        }).sort((a, b) => a.date.localeCompare(b.date));
        if (!controller.signal.aborted) setState({ status: points.length ? "ready" : "missing", points });
      }).catch(() => { if (!controller.signal.aborted) setState({ status: "missing", points: [] }); });
    return () => controller.abort();
  }, [code]);
  return <section className="os-panel">
    <h4>既有歷史收盤走勢</h4>
    <p className="os-caption">沿用既有歷史資料管線，來源可能含官方資料與 FinMind 補強；缺值不補造。</p>
    {state.status === "ready" ? <>
      <p className="os-caption">{state.points[0].date} — {state.points.at(-1)?.date} · {state.points.length} 筆</p>
      <div className="os-local-chart" aria-label={`${code} 歷史收盤價走勢`}>
        <ResponsiveContainer width="100%" height="100%"><LineChart data={state.points} margin={{ top: 10, right: 15, bottom: 0, left: 0 }}>
          <XAxis dataKey="date" tickFormatter={v => String(v).slice(5)} minTickGap={40} />
          <YAxis domain={["auto", "auto"]} width={60} /><Tooltip />
          <Line dataKey="close" name="收盤價 TWD" stroke="#2d7f73" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={false} />
        </LineChart></ResponsiveContainer>
      </div>
    </> : <p className="os-empty" role="status">{state.status === "loading" ? "正在讀取歷史走勢…" : "此標的尚無可用的歷史走勢檔，可前往個股雷達查看其他已備資料。"}</p>}
  </section>;
}
