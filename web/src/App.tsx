import { useEffect, useMemo, useState } from "react";

type MenuKey =
  | "rotation"
  | "flow"
  | "strength"
  | "map"
  | "stock"
  | "bigMoney"
  | "chips"
  | "watchlist"
  | "alerts"
  | "learn";

type DatasetStatus = "loading" | "ready" | "missing" | "error";

type DatasetBox = {
  key: string;
  label: string;
  path: string;
  status: DatasetStatus;
  data: Record<string, unknown> | null;
};

type SectorRow = {
  sector_name: string;
  name?: string;
  rank?: number;
  category?: string;
  net_1d_yi?: number;
  net_5d_yi?: number;
  net_20d_yi?: number;
  net_60d_yi?: number;
  accel?: number;
  position?: number;
  chg_1d?: number;
  chg_5d?: number;
  cp_score?: number;
  bottom_score?: number;
  alpha_score?: number;
  stock_count?: number;
  source?: string;
};

type StockRow = {
  stock_code?: string;
  stock_id?: string;
  stock_name?: string;
  sector_name?: string;
  alpha_score?: number;
  stock_alpha_v4?: number;
  net_1d_yi?: number;
  chg_1d?: number;
  reason?: string;
  risk_tags?: string[];
};

const MENU: Array<{ key: MenuKey; label: string; desc: string }> = [
  { key: "rotation", label: "輪動儀表板", desc: "總覽、泡泡圖、CP、抄底、回測" },
  { key: "flow", label: "資金流向", desc: "1/5/20/60 日法人淨流" },
  { key: "strength", label: "強勢排行", desc: "Sector / Stock Alpha v4" },
  { key: "map", label: "產業地圖", desc: "蜂巢圖、樹狀圖、熱力圖" },
  { key: "stock", label: "個股雷達", desc: "價格、法人、營收、籌碼趨勢" },
  { key: "bigMoney", label: "大戶動向", desc: "法人、主力 Proxy、夜盤" },
  { key: "chips", label: "籌碼分析", desc: "融資融券、借券、持股" },
  { key: "watchlist", label: "自選監控", desc: "觀察清單與條件監控" },
  { key: "alerts", label: "警示設定", desc: "價格、資金、Alpha 提醒" },
  { key: "learn", label: "教學專區", desc: "指標、來源、FAQ" }
];

const DATASETS: Array<Omit<DatasetBox, "status" | "data">> = [
  { key: "sectorRotation", label: "Sector Rotation", path: "/data/sector_rotation_latest.json" },
  { key: "cpRanking", label: "CP Ranking", path: "/data/cp_ranking_latest.json" },
  { key: "bottomFishing", label: "Bottom Fishing", path: "/data/bottom_fishing_latest.json" },
  { key: "recommendations", label: "Recommendations v4", path: "/data/recommendations_v4_latest.json" },
  { key: "backtest", label: "Backtest v4", path: "/data/backtest_v4_summary.json" },
  { key: "sectorAlpha", label: "Sector Alpha", path: "/data/sector_alpha_score.json" },
  { key: "stockAlpha", label: "Stock Alpha v4", path: "/data/stock_alpha_v4_latest.json" },
  { key: "futuresAfterHours", label: "台指期夜盤", path: "/data/futures_after_hours_latest.json" },
  { key: "chipAnalysis", label: "籌碼分析", path: "/data/chip_analysis_latest.json" },
  { key: "watchlist", label: "自選監控", path: "/data/watchlist_latest.json" }
];

function App() {
  const [active, setActive] = useState<MenuKey>(initialView());
  const [datasets, setDatasets] = useState<Record<string, DatasetBox>>({});
  const [selectedSector, setSelectedSector] = useState<string>("");
  const [stockId, setStockId] = useState(initialStockId());

  useEffect(() => {
    const next: Record<string, DatasetBox> = {};
    DATASETS.forEach((item) => {
      next[item.key] = { ...item, status: "loading", data: null };
    });
    setDatasets(next);

    DATASETS.forEach((item) => {
      fetch(`${item.path}?t=${Date.now()}`, { cache: "no-store" })
        .then((res) => {
          if (res.status === 404) return { status: "missing" as DatasetStatus, data: null };
          if (!res.ok) return { status: "error" as DatasetStatus, data: null };
          return res.json().then((data) => ({ status: "ready" as DatasetStatus, data }));
        })
        .then(({ status, data }) => {
          setDatasets((prev) => ({ ...prev, [item.key]: { ...item, status, data } }));
        })
        .catch(() => {
          setDatasets((prev) => ({ ...prev, [item.key]: { ...item, status: "error", data: null } }));
        });
    });
  }, []);

  const sidebarSource = datasets.sectorRotation?.data ?? null;
  const sourceDate = getDate(sidebarSource) ?? "等待資料";
  const marketChange = getNumber(sidebarSource, ["market_chg_1d", "market_change_pct", "index_change_pct"]);

  return (
    <div className="alpha-app">
      <aside className="alpha-sidebar">
        <Brand />
        <nav className="alpha-nav">
          {MENU.map((item) => (
            <button className={active === item.key ? "active" : ""} key={item.key} type="button" onClick={() => setActive(item.key)}>
              <span>{item.label}</span>
              <small>{item.desc}</small>
            </button>
          ))}
        </nav>
        <MarketStatus date={sourceDate} marketChange={marketChange} />
      </aside>
      <main className="alpha-main">
        <TopBar active={active} datasets={datasets} />
        <PageRouter active={active} datasets={datasets} selectedSector={selectedSector} setSelectedSector={setSelectedSector} stockId={stockId} setStockId={setStockId} />
      </main>
    </div>
  );
}

function PageRouter(props: {
  active: MenuKey;
  datasets: Record<string, DatasetBox>;
  selectedSector: string;
  setSelectedSector: (value: string) => void;
  stockId: string;
  setStockId: (value: string) => void;
}) {
  if (props.active === "rotation") return <RotationDashboard {...props} />;
  if (props.active === "flow") return <FlowPage {...props} />;
  if (props.active === "strength") return <StrengthPage {...props} />;
  if (props.active === "map") return <IndustryMapPage {...props} />;
  if (props.active === "stock") return <StockRadarPage {...props} />;
  if (props.active === "bigMoney") return <BigMoneyPage {...props} />;
  if (props.active === "chips") return <ChipAnalysisPage {...props} />;
  if (props.active === "watchlist") return <WatchlistPage {...props} />;
  if (props.active === "alerts") return <AlertsPage />;
  return <LearningPage />;
}

function RotationDashboard({ datasets, setSelectedSector }: { datasets: Record<string, DatasetBox>; setSelectedSector: (value: string) => void }) {
  const rotation = datasets.sectorRotation;
  const cp = datasets.cpRanking;
  const bottom = datasets.bottomFishing;
  const rec = datasets.recommendations;
  const backtest = datasets.backtest;
  const sectors = rows<SectorRow>(rotation?.data, ["sectors", "records", "items"]);
  const cpRows = rows<SectorRow>(cp?.data, ["records", "items", "sectors"]);
  const bottomRows = rows<SectorRow>(bottom?.data, ["records", "items", "sectors"]);
  const recRows = rows<StockRow>(rec?.data, ["records", "items", "recommendations"]);

  return (
    <section className="page-stack">
      <HeroOverview dataset={rotation} sectors={sectors} />
      <NightFuturesCard dataset={datasets.futuresAfterHours} />
      <div className="layout-3">
        <BubbleQuadrant dataset={rotation} sectors={sectors} onPick={setSelectedSector} />
        <RankingCard title="CP 值排行" dataset={cp} rows={cpRows} valueKey="cp_score" />
        <RankingCard title="抄底偵測" dataset={bottom} rows={bottomRows} valueKey="bottom_score" />
      </div>
      <div className="layout-2">
        <StockRecommendation dataset={rec} rows={recRows} />
        <BacktestSummary dataset={backtest} />
      </div>
    </section>
  );
}

function FlowPage({ datasets }: { datasets: Record<string, DatasetBox> }) {
  const dataset = datasets.sectorRotation;
  const sectorRows = rows<SectorRow>(dataset?.data, ["sector_daily_flow", "sectors", "records"]);
  return (
    <section className="page-stack">
      <SectionHeader title="資金流向" desc="展示 1 / 5 / 20 / 60 日法人淨買超，並拆分外資、投信、自營商貢獻。" dataset={dataset} />
      <TabBar items={["全部產業", "上市", "上櫃", "自訂主題"]} />
      <DataTable dataset={dataset} rows={sectorRows} columns={["sector_name", "net_1d_yi", "net_5d_yi", "net_20d_yi", "net_60d_yi", "accel", "chg_1d"]} labels={["產業", "1日", "5日", "20日", "60日", "加速度", "漲跌幅"]} />
    </section>
  );
}

function StrengthPage({ datasets }: { datasets: Record<string, DatasetBox> }) {
  const sector = datasets.sectorAlpha;
  const stock = datasets.stockAlpha;
  const sectorRows = rows<SectorRow>(sector?.data, ["records", "items", "sectors"]);
  const stockRows = rows<StockRow>(stock?.data, ["records", "items", "stocks"]);
  return (
    <section className="page-stack">
      <SectionHeader title="強勢排行" desc="依 Sector Alpha v4、Stock Alpha v4、報酬率、相對強弱與基本面因子排序。" dataset={stock} />
      <TabBar items={["Alpha 分數", "法人淨買超", "成交值放大", "月營收成長", "財報品質"]} />
      <div className="layout-2"><RankingCard title="Sector Alpha" dataset={sector} rows={sectorRows} valueKey="alpha_score" /><StockRecommendation title="Stock Alpha v4" dataset={stock} rows={stockRows} /></div>
    </section>
  );
}

function IndustryMapPage({ datasets, setSelectedSector }: { datasets: Record<string, DatasetBox>; setSelectedSector: (value: string) => void }) {
  const dataset = datasets.sectorRotation;
  const sectors = rows<SectorRow>(dataset?.data, ["sectors", "records", "items"]);
  return (
    <section className="page-stack">
      <SectionHeader title="產業地圖" desc="以蜂巢圖 / 樹狀圖 / 熱力圖呈現產業與子產業，面積代表成交值或市值，顏色代表資金淨流或報酬。" dataset={dataset} />
      <TabBar items={["法人淨買超", "CP 值", "抄底分數", "報酬率"]} />
      <div className="honeycomb-map">{sectors.slice(0, 40).map((sector, index) => <button key={`${sector.sector_name}-${index}`} type="button" onClick={() => setSelectedSector(sector.sector_name || sector.name || "")}>{sector.sector_name || sector.name}<span>{fmtNumber(sector.net_1d_yi)}</span></button>)}</div>
    </section>
  );
}

function StockRadarPage({ datasets, stockId, setStockId }: { datasets: Record<string, DatasetBox>; stockId: string; setStockId: (value: string) => void }) {
  const stock = datasets.stockAlpha;
  const trendsPath = `/data/trends/${stockId || "2330"}.json`;
  return (
    <section className="page-stack">
      <SectionHeader title="個股雷達" desc="價格、成交值、法人買賣、融資融券、營收財報、Alpha v4 拆解與風險扣分。" dataset={stock} />
      <div className="stock-search"><input value={stockId} onChange={(event) => setStockId(event.target.value)} placeholder="輸入股票代號，例如 2330" /><span>趨勢資料：{trendsPath}</span></div>
      <MissingAwarePanel dataset={stock} title="Stock Alpha v4 拆解" />
      <div className="chart-grid"><ChartPlaceholder title="價格趨勢" /><ChartPlaceholder title="法人買賣超趨勢" /><ChartPlaceholder title="融資融券變化" /><ChartPlaceholder title="月營收 / 財報趨勢" /></div>
    </section>
  );
}

function BigMoneyPage({ datasets }: { datasets: Record<string, DatasetBox> }) {
  return (
    <section className="page-stack">
      <SectionHeader title="大戶動向" desc="統合法人買賣超、主力資金 Proxy、分點、融資融券與台指期夜盤。" dataset={datasets.futuresAfterHours} />
      <div className="layout-2"><NightFuturesCard dataset={datasets.futuresAfterHours} /><MissingAwarePanel dataset={datasets.sectorRotation} title="法人與主力 Proxy 排行" /></div>
    </section>
  );
}

function ChipAnalysisPage({ datasets }: { datasets: Record<string, DatasetBox> }) {
  return (
    <section className="page-stack">
      <SectionHeader title="籌碼分析" desc="融資餘額、融券餘額、借券餘額、外資持股比率、分點集中度與股價 / Alpha 對照。" dataset={datasets.chipAnalysis} />
      <div className="chart-grid"><MissingAwarePanel dataset={datasets.chipAnalysis} title="Margin Purchase Short Sale" /><ChartPlaceholder title="Securities Lending" /><ChartPlaceholder title="Shareholding" /><ChartPlaceholder title="Chip Heatmap" /></div>
    </section>
  );
}

function WatchlistPage({ datasets }: { datasets: Record<string, DatasetBox> }) {
  return (
    <section className="page-stack">
      <SectionHeader title="自選監控" desc="顯示自選產業與個股的價格、Alpha、資金淨流、法人籌碼與風險標籤。" dataset={datasets.watchlist} />
      <MissingAwarePanel dataset={datasets.watchlist} title="我的觀察清單" />
      <RuleBuilder />
    </section>
  );
}

function AlertsPage() {
  return <StaticPage title="警示設定" desc="警示條件將保存在後端資料庫，需使用者隔離，不涉及自動下單。"><RuleBuilder /></StaticPage>;
}

function LearningPage() {
  return <StaticPage title="教學專區" desc="靜態內容，可使用 Markdown 或 CMS 編輯。"><div className="learning-grid"><GuideCard title="四象限怎麼看" /><GuideCard title="CP 值代表什麼" /><GuideCard title="抄底偵測風險" /><GuideCard title="資料來源說明" /></div></StaticPage>;
}

function Brand() {
  return <div className="brand"><div className="brand-logo">A</div><div><strong>台股 Alpha</strong><span>Capital Rotation</span></div></div>;
}

function MarketStatus({ date, marketChange }: { date: string; marketChange: number | null }) {
  return <div className="market-status"><span>大盤漲跌</span><strong>{marketChange === null ? "資料尚未更新" : fmtPct(marketChange)}</strong><small>資料日期 {date}</small></div>;
}

function TopBar({ active, datasets }: { active: MenuKey; datasets: Record<string, DatasetBox> }) {
  const ready = Object.values(datasets).filter((d) => d.status === "ready").length;
  const missing = Object.values(datasets).filter((d) => d.status === "missing").length;
  return <header className="topbar"><div><h1>{MENU.find((item) => item.key === active)?.label}</h1><p>{MENU.find((item) => item.key === active)?.desc}</p></div><div className="topbar-meta"><span>{ready} 份資料已載入</span><span>{missing} 份資料未更新</span></div></header>;
}

function HeroOverview({ dataset, sectors }: { dataset?: DatasetBox; sectors: SectorRow[] }) {
  const leader = sectors[0];
  return <section className="hero-card">{dataset?.status !== "ready" ? <MissingState dataset={dataset} /> : <><div><span className="eyebrow">Rotation Dashboard</span><h2>{leader?.sector_name || leader?.name || "資金輪動"}<br />資金領跑</h2><p>市場狀態、資金方向、四象限、CP 值、抄底偵測與回測摘要整合在同一個入口。</p></div><div className="hero-metrics"><Metric label="1日買賣超" value={fmtYi(leader?.net_1d_yi)} /><Metric label="5日買賣超" value={fmtYi(leader?.net_5d_yi)} /><Metric label="20日買賣超" value={fmtYi(leader?.net_20d_yi)} /><Metric label="漲跌幅" value={fmtPct(leader?.chg_1d)} /></div></>}</section>;
}

function NightFuturesCard({ dataset }: { dataset?: DatasetBox }) {
  if (dataset?.status !== "ready") return <MissingAwarePanel dataset={dataset} title="台指期夜盤指數" />;
  const latest = (dataset.data?.latest || {}) as Record<string, unknown>;
  const records = rows<Record<string, unknown>>(dataset.data, ["records"]);
  return (
    <section className="panel night-futures-card">
      <SectionTitle title="台指期夜盤指數" meta="TX after_market" />
      <div className="night-futures-grid">
        <Metric label="夜盤指數" value={fmtNumber(latest.night_index || latest.settlement_price || latest.close)} />
        <Metric label="漲跌" value={fmtNumber(latest.spread)} />
        <Metric label="漲跌幅" value={fmtPct(latest.spread_per)} />
        <Metric label="成交量" value={fmtNumber(latest.volume)} />
        <Metric label="未沖銷量" value={fmtNumber(latest.open_interest)} />
        <Metric label="合約月份" value={String(latest.contract_date || "N/A")} />
      </div>
      <div className="night-chart" aria-label="最近 30 日台指期夜盤走勢">
        {records.slice(-30).map((row, index) => {
          const value = Number(row.night_index || row.close || 0);
          const values = records.slice(-30).map((item) => Number(item.night_index || item.close || 0)).filter(Number.isFinite);
          const min = Math.min(...values);
          const max = Math.max(...values);
          const y = max === min ? 50 : 88 - ((value - min) / (max - min)) * 72;
          const x = records.length <= 1 ? 50 : (index / Math.max(records.slice(-30).length - 1, 1)) * 100;
          return <span key={`${row.date}-${index}`} style={{ left: `${x}%`, top: `${y}%` }} title={`${row.date}: ${value}`} />;
        })}
      </div>
      <div className="source-line">來源：{String(dataset.data?.source || "FinMind")} · 資料日期 {String(dataset.data?.as_of_date || "N/A")} · {String(dataset.data?.selection_method || "main contract")}</div>
    </section>
  );
}

function BubbleQuadrant({ dataset, sectors, onPick }: { dataset?: DatasetBox; sectors: SectorRow[]; onPick: (value: string) => void }) {
  if (dataset?.status !== "ready") return <MissingAwarePanel dataset={dataset} title="四象限泡泡圖" />;
  return <section className="panel xl"><SectionTitle title="四象限泡泡圖" meta="主力 / 輪動 / 觀望 / 退潮" /><div className="bubble-stage">{sectors.slice(0, 36).map((s, i) => <button key={`${s.sector_name}-${i}`} type="button" style={{ left: `${Math.max(8, Math.min(90, 50 + (s.net_5d_yi || 0) / 8))}%`, top: `${Math.max(8, Math.min(88, 92 - (s.position || 40)))}%` }} onClick={() => onPick(s.sector_name || s.name || "")}>{s.sector_name || s.name}</button>)}</div></section>;
}

function RankingCard({ title, dataset, rows, valueKey }: { title: string; dataset?: DatasetBox; rows: SectorRow[]; valueKey: keyof SectorRow }) {
  if (dataset?.status !== "ready") return <MissingAwarePanel dataset={dataset} title={title} />;
  return <section className="panel"><SectionTitle title={title} meta={dataset?.label} />{rows.slice(0, 8).map((row, index) => <div className="rank-row" key={`${title}-${index}`}><span>{index + 1}</span><strong>{row.sector_name || row.name}</strong><em>{fmtNumber(row[valueKey] as number | undefined)}</em></div>)}</section>;
}

function StockRecommendation({ title = "今日觀察標的 Top 10", dataset, rows }: { title?: string; dataset?: DatasetBox; rows: StockRow[] }) {
  if (dataset?.status !== "ready") return <MissingAwarePanel dataset={dataset} title={title} />;
  return <section className="panel"><SectionTitle title={title} meta="中性觀察，不是買賣建議" />{rows.slice(0, 10).map((row, index) => <div className="stock-row" key={`${title}-${index}`}><strong>{row.stock_code || row.stock_id}</strong><span>{row.stock_name || row.sector_name || "N/A"}</span><em>{fmtNumber(row.stock_alpha_v4 || row.alpha_score)}</em><small>{row.reason || "資料管線預計算"}</small></div>)}</section>;
}

function BacktestSummary({ dataset }: { dataset?: DatasetBox }) {
  if (dataset?.status !== "ready") return <MissingAwarePanel dataset={dataset} title="回測效能摘要" />;
  return <section className="panel"><SectionTitle title="回測效能摘要" meta="12 個月週期換倉" /><pre>{JSON.stringify(dataset.data, null, 2).slice(0, 900)}</pre></section>;
}

function DataTable<T extends Record<string, unknown>>({ dataset, rows, columns, labels }: { dataset?: DatasetBox; rows: T[]; columns: string[]; labels: string[] }) {
  if (dataset?.status !== "ready") return <MissingAwarePanel dataset={dataset} title="資料表" />;
  return <section className="panel table-panel"><div className="data-table" style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(120px, 1fr))` }}>{labels.map((label) => <b key={label}>{label}</b>)}{rows.slice(0, 40).flatMap((row, i) => columns.map((col) => <span key={`${i}-${col}`}>{formatCell(row[col])}</span>))}</div></section>;
}

function SectionHeader({ title, desc, dataset }: { title: string; desc: string; dataset?: DatasetBox }) {
  return <section className="section-header"><div><h2>{title}</h2><p>{desc}</p></div><DatasetBadge dataset={dataset} /></section>;
}

function SectionTitle({ title, meta }: { title: string; meta?: string }) {
  return <div className="section-title"><h3>{title}</h3>{meta ? <span>{meta}</span> : null}</div>;
}

function TabBar({ items }: { items: string[] }) {
  return <div className="tabs">{items.map((item, index) => <button className={index === 0 ? "active" : ""} type="button" key={item}>{item}</button>)}</div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}

function getRows<T extends Record<string, unknown>>(data: any): T[] {
  const rows = data?.records || data?.items || data?.sectors || [];
  return Array.isArray(rows) ? rows as T[] : [];
}

function MissingAwarePanel({ dataset, title }: { dataset?: DatasetBox; title: string }) {
  const rows = getRows<Record<string, unknown>>(dataset?.data);
  const isUnavailable = dataset?.status !== "ready" || dataset?.data?.status === "error";
  if (isUnavailable) return <section className="panel"><SectionTitle title={title} meta={dataset?.label} /><MissingState dataset={dataset} /></section>;
  return (
    <section className="panel">
      <SectionTitle title={title} meta={dataset?.label} />
      {rows.length ? rows.slice(0, 8).map((row, index) => (
        <div className="rank-row" key={`${title}-${index}`}>
          <span>{index + 1}</span>
          <strong>{String(row.sector_name || row.stock_name || row.stock_code || row.stock_id || row.name || "N/A")}</strong>
          <em>{formatCell(row.net_1d_yi ?? row.stock_alpha_v4 ?? row.alpha_score ?? row.cp_score ?? row.bottom_score)}</em>
        </div>
      )) : <div className="missing"><strong>資料已載入</strong><span>此資料集目前沒有可列表資料。</span></div>}
    </section>
  );
}

function MissingState({ dataset }: { dataset?: DatasetBox }) {
  if (dataset?.status === "loading") return <div className="missing">資料載入中</div>;
  return <div className="missing"><strong>資料尚未更新，請稍後再試</strong><span>需要資料：{dataset?.path || "public/data/*.json"}</span><small>前端不使用假資料，也不直接呼叫後端 API。</small></div>;
}

function DatasetBadge({ dataset }: { dataset?: DatasetBox }) {
  const date = getDate(dataset?.data);
  return <div className={`dataset-badge ${dataset?.status || "missing"}`}><strong>{dataset?.status || "missing"}</strong><span>{date || dataset?.path || "等待資料"}</span></div>;
}

function ChartPlaceholder({ title }: { title: string }) {
  return <section className="panel chart-placeholder"><SectionTitle title={title} meta="等待 public/data JSON" /><div /></section>;
}

function RuleBuilder() {
  return <section className="panel rule-builder"><SectionTitle title="條件設定" meta="只做提醒，不做交易" /><div className="rule-grid"><span>標的</span><span>條件</span><span>門檻</span><span>通知</span><button type="button">新增規則</button></div></section>;
}

function StaticPage({ title, desc, children }: { title: string; desc: string; children: React.ReactNode }) {
  return <section className="page-stack"><SectionHeader title={title} desc={desc} />{children}</section>;
}

function GuideCard({ title }: { title: string }) { return <article className="panel guide-card"><h3>{title}</h3><p>以 Markdown 或 CMS 維護內容。</p></article>; }

function rows<T>(data: Record<string, unknown> | null | undefined, keys: string[]): T[] {
  if (!data) return [];
  for (const key of keys) {
    const value = data[key];
    if (Array.isArray(value)) return value as T[];
  }
  return [];
}

function getDate(data: Record<string, unknown> | null | undefined): string | null {
  if (!data) return null;
  return String(data.data_timestamp || data.as_of_date || data.date || data.source_updated_at || "") || null;
}

function getNumber(data: Record<string, unknown> | null | undefined, keys: string[]): number | null {
  if (!data) return null;
  for (const key of keys) {
    const value = data[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}

function fmtNumber(value: unknown): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "N/A";
  return value.toFixed(2);
}

function fmtYi(value: unknown): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "N/A";
  return `${value.toFixed(2)} 億`;
}

function fmtPct(value: unknown): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "N/A";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatCell(value: unknown): string {
  if (typeof value === "number") return value.toFixed(2);
  if (Array.isArray(value)) return value.join(", ");
  if (value === null || value === undefined) return "N/A";
  return String(value);
}

function initialView(): MenuKey {
  const path = window.location.pathname;
  if (path.startsWith("/stock/")) return "stock";
  return "rotation";
}

function initialStockId(): string {
  const match = window.location.pathname.match(/\/stock\/([^/]+)/);
  return match?.[1] || "2330";
}

export default App;
