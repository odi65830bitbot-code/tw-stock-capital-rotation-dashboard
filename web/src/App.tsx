import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import type { CSSProperties } from "react";
import { Area, AreaChart, LineChart, Line, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from "recharts";
import { motion, AnimatePresence } from "framer-motion";
import type { Sector, SectorStock } from "./types";
import { CreatureCard } from "./components/CreatureCard";
import type { CreatureCardData, FlowStatus, RecommendationStatus } from "./lib/creatureCardModel";

type MenuKey =
  | "charts"
  | "rotation"
  | "flow"
  | "strength"
  | "map"
  | "stock"
  | "bigMoney"
  | "chips"
  | "watchlist"
  | "alerts"
  | "goldenExit"
  | "portfolio"
  | "news"
  | "learn";

type PortfolioItem = {
  id: string;
  shares: number;
  buyPrice: number;
};

type DatasetStatus = "loading" | "ready" | "missing" | "error";

type DatasetBox = {
  key: string;
  label: string;
  path: string;
  fallbackPaths?: string[];
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
  trade_value_yi?: number;
  stock_count?: number;
  source?: string;
  stocks?: string[];
};

type StockRow = {
  stock_code?: string;
  stock_id?: string;
  stock_name?: string;
  name?: string;
  sector_name?: string;
  industry?: string;
  alpha_score?: number;
  stock_alpha_v4?: number;
  net_1d_yi?: number;
  net_5d_yi?: number;
  net_20d_yi?: number;
  chg_1d?: number;
  change_pct?: number;
  reason?: string;
  risk_tags?: string[];
  tags?: string[];
  Alpha_Score_v6?: number;
  Alpha_Score_v5?: number;
  stock_alpha_v5?: number;
  sentiment_temperature?: number;
  sentiment_score?: number;
  Vol_20d?: number;
  market?: string;
  close?: number;
  trade_value_yi?: number;
  trade_value_twd?: number;
  three_party_net_shares?: number | null;
  rank?: number;
  sector_rank?: number;
  suggested_status?: string;
};

type EtfConstituentRow = {
  stock_code?: string;
  stock_id?: string;
  stock_name?: string;
  weight_pct?: number;
  shares?: number;
  market_value_yi?: number;
};

type EtfHoldingRow = {
  etf_code?: string;
  etf_id?: string;
  etf_name?: string;
  as_of_date?: string;
  holdings_count?: number;
  weight_coverage_pct?: number;
  source?: string[];
  constituents?: EtfConstituentRow[];
};

type SectorFlowHistoryRow = {
  date: string;
  sector: string;
  foreign: number;
  trust: number;
  dealer: number;
  total: number;
};

type SectorFlowHistoryPayload = {
  status?: string;
  as_of_date?: string;
  dates?: string[];
  sectors?: string[];
  data?: SectorFlowHistoryRow[];
  records?: SectorFlowHistoryRow[];
};

type SectorChartView = "heatmap" | "trend";
type PlanetMetric = "1d" | "5d" | "20d" | "volume";
type SankeyRange = "today" | "week" | "month";

type TrendPricePoint = {
  trade_date: string;
  close: number;
  ma5: number;
  ma20: number;
  ma60: number;
};

type TrendFlowPoint = {
  trade_date: string;
  foreign_net_shares: number | null;
  trustee_net_shares: number | null;
  dealer_net_shares: number | null;
  foreign_5d?: number;
  trust_5d?: number;
};

type TrendValuePoint = {
  trade_date: string;
  trade_value_twd: number;
  trade_value_ma20: number;
  trade_value_multiple: number;
};

type TrendAlphaPoint = {
  trade_date: string;
  stock_alpha_score: number;
  alpha_score_total: number;
};

type StockTrendPayload = {
  stock_id: string;
  stock_name: string;
  market: string;
  industry: string;
  generated_at: string;
  price?: TrendPricePoint[];
  trade_value?: TrendValuePoint[];
  institutional_flow?: TrendFlowPoint[];
  alpha?: TrendAlphaPoint[];
  recommendation?: {
    first_recommend_date: string;
    recommend_close: number;
    current_price: number;
    post_recommend_return: number;
    still_recommended: boolean;
  };
};

type GlobalNews = {
  title: string;
  link: string;
  pubDate: string;
};

const MENU: Array<{ key: MenuKey; label: string; desc: string }> = [
  { key: "rotation", label: "輪動儀表板", desc: "總覽、CP、抄底" },
  { key: "charts", label: "資金圖表", desc: "行星圖、河流與法人流向" },
  { key: "flow", label: "資金流向", desc: "1/5/20/60 日法人淨流" },
  { key: "strength", label: "強勢排行", desc: "Sector / Stock Alpha v4" },
  { key: "map", label: "產業地圖", desc: "板塊清單、熱力圖、成分股" },
  { key: "stock", label: "個股雷達", desc: "價格、法人、營收、籌碼趨勢" },
  { key: "bigMoney", label: "大戶動向", desc: "法人、主力 Proxy、夜盤" },
  { key: "chips", label: "籌碼分析", desc: "融資融券、借券、持股" },
  { key: "watchlist", label: "自選監控", desc: "觀察清單與條件監控" },
  { key: "portfolio", label: "我的持股", desc: "持股標的與買賣建議" },
  { key: "alerts", label: "警示設定", desc: "價格、資金、Alpha 提醒" },
  { key: "goldenExit", label: "黃金逃頂", desc: "波段防守價與明日壓力價" },
  { key: "news", label: "全球財經", desc: "各國重點財經新聞" },
  { key: "learn", label: "教學專區", desc: "指標、來源、FAQ" }
];

const DATASETS: Array<Omit<DatasetBox, "status" | "data">> = [
  { key: "dataManifest", label: "資料批次 Manifest", path: "/data/data_manifest.json" },
  { key: "sectorRotation", label: "Sector Rotation", path: "/data/sector_rotation_latest.json" },
  { key: "sectorFlowHistory", label: "Sector Flow History", path: "/data/sector_flow_history.json" },
  { key: "sectorConstituents", label: "Sector Constituents", path: "/data/sector_constituents_latest.json" },
  { key: "stockLookup", label: "Stock Lookup", path: "/data/stock_lookup_latest.json" },
  { key: "etfHoldings", label: "ETF Holdings", path: "/data/etf_holdings_latest.json" },
  { key: "cpRanking", label: "CP Ranking", path: "/data/cp_ranking_latest.json" },
  { key: "bottomFishing", label: "Bottom Fishing", path: "/data/bottom_fishing_latest.json" },
  { key: "recommendations", label: "Recommendations v5", path: "/data/recommendations_v5_latest.json", fallbackPaths: ["/data/recommendations_latest.json"] },
  { key: "recommendationsV6", label: "Recommendations v6", path: "/data/recommendations_v6_latest.json" },
  { key: "backtest", label: "Backtest v4", path: "/data/backtest_v4_summary.json" },
  { key: "sectorAlpha", label: "Sector Alpha", path: "/data/sector_alpha_score.json" },
  { key: "stockAlpha", label: "Stock Alpha v4", path: "/data/stock_alpha_v4_latest.json" },
  { key: "futuresAfterHours", label: "台指期夜盤", path: "/data/futures_after_hours_latest.json" },
  { key: "chipAnalysis", label: "籌碼分析", path: "/data/chip_analysis_latest.json" },
  { key: "goldenExit", label: "黃金逃頂", path: "/data/golden_exit_latest.json" },
  { key: "watchlist", label: "自選監控", path: "/data/watchlist_latest.json" },
  { key: "marketData", label: "大盤資訊", path: "/data/market_latest.json" }
];

const SECTOR_CHART_TABS: Array<{ key: SectorChartView; label: string }> = [
  { key: "heatmap", label: "資金熱力矩陣" },
  { key: "trend", label: "產業流量趨勢" }
];

const STREAM_COLORS = ["#27e083", "#5ad0ff", "#e4b125", "#ff8a5c", "#b58cff", "#78f0c4", "#f06f9f", "#9fb7ff"];

function getStockMarket(code: string, stockAlphaData: any): string {
  if (stockAlphaData?.records) {
    const found = stockAlphaData.records.find(
      (r: any) => String(r.stock_code) === String(code) || String(r.stock_id) === String(code)
    );
    if (found?.market) return found.market;
  }
  return "UNKNOWN";
}

function getSectorMarket(stocks: string[] | undefined, stockAlphaData: any): "TWSE" | "TPEX" | "全部" {
  if (!stocks || stocks.length === 0) return "全部";
  const market = getStockMarket(stocks[0], stockAlphaData);
  if (market === "TWSE" || market === "TPEX") return market;
  return "全部";
}

function normalizeSectorName(name: string | undefined): string {
  if (!name) return "";
  return name.replace(/[【】\[\]\(\)\s]/g, "").trim();
}

function comparableSectorName(name: string | undefined): string {
  return normalizeSectorName(name)
    .replace(/金融保險/g, "銀行金融")
    .replace(/週邊/g, "周邊")
    .replace(/通訊/g, "通信")
    .replace(/化學/g, "化工")
    .replace(/工業$/g, "")
    .replace(/產業$/g, "")
    .replace(/業$/g, "");
}

function sectorNameMatches(left: string | undefined, right: string | undefined): boolean {
  const a = comparableSectorName(left);
  const b = comparableSectorName(right);
  if (!a || !b) return false;
  return a === b || a.includes(b) || b.includes(a);
}

function sectorFlowHistoryRows(payload: Record<string, unknown> | null | undefined): SectorFlowHistoryRow[] {
  const source = payload as SectorFlowHistoryPayload | null | undefined;
  const data = Array.isArray(source?.data) ? source.data : Array.isArray(source?.records) ? source.records : [];
  return data
    .filter((row) => row?.date && row?.sector)
    .map((row) => ({
      date: String(row.date),
      sector: String(row.sector),
      foreign: Number(row.foreign) || 0,
      trust: Number(row.trust) || 0,
      dealer: Number(row.dealer) || 0,
      total: Number(row.total) || 0
    }));
}

function recentFlowDates(rows: SectorFlowHistoryRow[], days: number): string[] {
  return [...new Set(rows.map((row) => row.date))].sort().slice(-days);
}

function topFlowSectors(rows: SectorFlowHistoryRow[], dates: string[], limit: number): string[] {
  const dateSet = new Set(dates);
  const scores = new Map<string, { positive: number; absolute: number }>();
  rows.forEach((row) => {
    if (!dateSet.has(row.date)) return;
    const current = scores.get(row.sector) || { positive: 0, absolute: 0 };
    current.positive += Math.max(row.total, 0);
    current.absolute += Math.abs(row.total);
    scores.set(row.sector, current);
  });
  return [...scores.entries()]
    .sort((a, b) => (b[1].positive || b[1].absolute) - (a[1].positive || a[1].absolute))
    .slice(0, limit)
    .map(([sector]) => sector);
}

function flowColor(value: number, maxAbs: number): string {
  const ratio = maxAbs > 0 ? Math.min(Math.abs(value) / maxAbs, 1) : 0;
  if (value > 0) return `hsl(145 72% ${24 + ratio * 28}%)`;
  if (value < 0) return `hsl(9 72% ${30 + ratio * 24}%)`;
  return "hsl(150 4% 22%)";
}

function compactShares(value: number): string {
  // 將股數轉為張數 (1張 = 1000股)
  const vol = value / 1000;
  if (Math.abs(vol) >= 100_000_000) return `${(vol / 100_000_000).toFixed(1)}億張`;
  if (Math.abs(vol) >= 10_000) return `${(vol / 10_000).toFixed(1)}萬張`;
  return `${Math.round(vol).toLocaleString("zh-TW")}張`;
}

function stockCode(row: Partial<StockRow> | Record<string, unknown>): string {
  return String(row.stock_code || row.stock_id || "").trim();
}

function stockName(row: Partial<StockRow> | Record<string, unknown>): string {
  return String(row.stock_name || row.name || "").trim();
}

function stockLabel(row: Partial<StockRow> | Record<string, unknown>): string {
  const code = stockCode(row);
  const name = stockName(row);
  if (!code && !name) return "N/A";
  return [code, name].filter(Boolean).join(" ");
}

function findStockBasic(datasets: Record<string, DatasetBox>, code: string): StockRow | undefined {
  const target = String(code || "").trim();
  if (!target) return undefined;
  const sources = [
    rows<StockRow>(datasets.stockLookup?.data, ["records", "items", "stocks"]),
    rows<StockRow>(datasets.stockAlpha?.data, ["records", "items", "stocks"]),
    rows<StockRow>(datasets.sectorConstituents?.data, ["records", "items", "stocks"]),
  ];
  for (const source of sources) {
    const match = source.find((row) => stockCode(row) === target);
    if (match) return match;
  }
  return undefined;
}

function isEtfCode(value: string | undefined): boolean {
  return /^00[0-9A-Z]{2,4}$/.test(String(value || "").trim().toUpperCase());
}

function findEtfHolding(datasets: Record<string, DatasetBox>, code: string): EtfHoldingRow | undefined {
  const target = String(code || "").trim().toUpperCase();
  if (!target) return undefined;
  return rows<EtfHoldingRow>(datasets.etfHoldings?.data, ["records", "items"]).find((row) => {
    const etfCode = String(row.etf_code || row.etf_id || "").trim().toUpperCase();
    return etfCode === target;
  });
}

function formatNewsDate(value: string): string {
  if (!value) return "時間未標記";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-TW", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function enrichStockRow(row: StockRow, stockAlphaRows: StockRow[]): StockRow {
  const code = stockCode(row);
  const match = stockAlphaRows.find((item) => stockCode(item) === code);
  if (!match) return row;
  return {
    ...match,
    ...row,
    stock_code: code || stockCode(match),
    stock_name: row.stock_name || match.stock_name,
    sector_name: row.sector_name || match.sector_name || match.industry,
    industry: row.industry || match.industry || match.sector_name,
    chg_1d: row.chg_1d ?? row.change_pct ?? match.chg_1d ?? match.change_pct,
    net_1d_yi: row.net_1d_yi ?? match.net_1d_yi,
    net_5d_yi: row.net_5d_yi ?? match.net_5d_yi,
    net_20d_yi: row.net_20d_yi ?? match.net_20d_yi,
  };
}

function stockNet1dYi(row: StockRow): number | undefined {
  if (typeof row.net_1d_yi === "number") return row.net_1d_yi;
  if (typeof row.three_party_net_shares === "number" && typeof row.close === "number") {
    return (row.three_party_net_shares * row.close) / 100000000;
  }
  return undefined;
}

function sectorConstituentRows(
  sectorName: string,
  datasets: Record<string, DatasetBox>,
  rotationData: Record<string, unknown> | null | undefined
): StockRow[] {
  if (!sectorName) return [];
  const stockAlphaRows = rows<StockRow>(datasets.stockAlpha?.data, ["records", "items", "stocks"]);
  const constituentRows = rows<StockRow>(datasets.sectorConstituents?.data, ["records", "items", "stocks"])
    .filter((row) => sectorNameMatches(row.sector_name || row.industry, sectorName))
    .map((row) => enrichStockRow(row, stockAlphaRows));

  if (constituentRows.length > 0) {
    return constituentRows.sort((a, b) => {
      const aFlow = stockNet1dYi(a) ?? 0;
      const bFlow = stockNet1dYi(b) ?? 0;
      return bFlow - aFlow;
    });
  }

  const rotationRows = rows<StockRow>(rotationData, ["stock_data"])
    .filter((row) => sectorNameMatches(row.sector_name || row.industry, sectorName))
    .map((row, idx) => enrichStockRow({ ...row, sector_rank: row.sector_rank || idx + 1 }, stockAlphaRows));

  if (rotationRows.length > 0) return rotationRows;

  return stockAlphaRows
    .filter((row) => sectorNameMatches(row.sector_name || row.industry, sectorName))
    .map((row, idx) => ({ ...row, sector_rank: row.sector_rank || row.rank || idx + 1 }));
}

function aggregateSectors(sectors: SectorRow[]): SectorRow[] {
  const grouped = new Map<string, SectorRow>();
  for (const sector of sectors) {
    const name = sector.sector_name || sector.name || "";
    if (!name) continue;
    const current = grouped.get(name);
    if (!current) {
      grouped.set(name, { ...sector, sector_name: name });
      continue;
    }
    grouped.set(name, {
      ...current,
      stock_count: (current.stock_count || 0) + (sector.stock_count || 0),
      net_1d_yi: (current.net_1d_yi || 0) + (sector.net_1d_yi || 0),
      net_5d_yi: (current.net_5d_yi || 0) + (sector.net_5d_yi || 0),
      net_20d_yi: (current.net_20d_yi || 0) + (sector.net_20d_yi || 0),
      net_60d_yi: (current.net_60d_yi || 0) + (sector.net_60d_yi || 0),
      trade_value_yi: (current.trade_value_yi || 0) + (sector.trade_value_yi || 0),
      chg_1d: current.chg_1d ?? sector.chg_1d,
      position: Math.max(current.position || 0, sector.position || 0),
    });
  }
  return [...grouped.values()].sort((a, b) => Math.abs(b.net_1d_yi || 0) - Math.abs(a.net_1d_yi || 0));
}

// ==========================================
// 0. Global Stock Dictionary (O(1) Lookup)
// ==========================================
export type StockDictData = {
  stock_code: string;
  stock_name: string;
  close: number;
  change_pct: number;
};

export function useStockDictionary(datasets: Record<string, DatasetBox>) {
  return useMemo(() => {
    const dict = new Map<string, StockDictData>();
    const sectorData = datasets.sectorConstituents?.data;
    const records = Array.isArray(sectorData?.records) ? sectorData.records : [];
    for (const r of records as any[]) {
      if (r.stock_code || r.stock_id) {
        const code = String(r.stock_code || r.stock_id);
        dict.set(code, {
          stock_code: code,
          stock_name: String(r.stock_name || "未知"),
          close: Number(r.close || 0),
          change_pct: Number(r.change_pct || 0)
        });
      }
    }
    return dict;
  }, [datasets.sectorConstituents]);
}

// ==========================================
// 1. TabBar 組件實作 (符合 Vibe 視覺美感)
// ==========================================
interface TabBarProps {
  items: string[];
  active: string;
  onChange: (value: string) => void;
}

function TabBar({ items, active, onChange }: TabBarProps) {
  return (
    <div
      className="tab-bar-container"
      style={{
        display: 'flex',
        gap: '6px',
        marginBottom: '20px',
        background: 'rgba(255, 255, 255, 0.03)',
        padding: '4px',
        borderRadius: '8px',
        width: 'fit-content',
        border: '1px solid rgba(255, 255, 255, 0.05)',
        position: 'relative'
      }}
    >
      {items.map((item) => {
        const isActive = active === item;
        return (
          <button
            key={item}
            type="button"
            onClick={() => onChange(item)}
            style={{
              position: 'relative',
              background: 'transparent',
              color: isActive ? '#0d1117' : 'var(--muted)',
              border: 'none',
              borderRadius: '6px',
              padding: '6px 16px',
              fontSize: '14px',
              fontWeight: '600',
              cursor: 'pointer',
              transition: 'color 0.2s ease',
              outline: 'none',
              zIndex: 1
            }}
          >
            {isActive && (
              <motion.div
                layoutId="tab-active-bg"
                style={{
                  position: 'absolute',
                  inset: 0,
                  background: 'var(--accent)',
                  borderRadius: '6px',
                  boxShadow: '0 2px 8px rgba(39, 224, 131, 0.25)',
                  zIndex: -1
                }}
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
              />
            )}
            <span style={{ position: 'relative', zIndex: 2 }}>{item}</span>
          </button>
        );
      })}
    </div>
  );
}

// ==========================================
// 2. PageRouter 組件實作 (連結各分頁面板)
// ==========================================
interface PageRouterProps {
  active: MenuKey;
  datasets: Record<string, DatasetBox>;
  selectedSector: string;
  setSelectedSector: (value: string) => void;
  stockId: string;
  setStockId: (value: string) => void;
  watchlist: string[];
  toggleWatch: (codeAndName: string) => void;
  portfolio: PortfolioItem[];
  setPortfolio: (p: PortfolioItem[]) => void;
  onNavigateToStock: (code: string) => void;
  onNavigateToSector: (sectorName: string) => void;
  globalNews: GlobalNews[];
}

function PageRouter({
  active,
  datasets,
  selectedSector,
  setSelectedSector,
  stockId,
  setStockId,
  watchlist,
  toggleWatch,
  portfolio,
  setPortfolio,
  onNavigateToStock,
  onNavigateToSector,
  globalNews
}: PageRouterProps) {
  switch (active) {
    case "rotation":
      return (
        <RotationDashboard
          datasets={datasets}
          onNavigateToStock={onNavigateToStock}
          onNavigateToSector={onNavigateToSector}
        />
      );
    case "charts":
      return (
        <ChartsPage
          datasets={datasets}
          onNavigateToStock={onNavigateToStock}
          onNavigateToSector={onNavigateToSector}
        />
      );
    case "flow":
      return (
        <FlowPage
          datasets={datasets}
          selectedSector={selectedSector}
          setSelectedSector={setSelectedSector}
          onNavigateToStock={onNavigateToStock}
        />
      );
    case "strength":
      return (
        <StrengthPage
          datasets={datasets}
          onNavigateToStock={onNavigateToStock}
          onNavigateToSector={onNavigateToSector}
        />
      );
    case "map":
      return (
        <IndustryMapPage
          datasets={datasets}
          selectedSector={selectedSector}
          setSelectedSector={setSelectedSector}
          onNavigateToStock={onNavigateToStock}
        />
      );
    case "stock":
      return (
        <StockRadarPage
          datasets={datasets}
          stockId={stockId}
          setStockId={setStockId}
          watchlist={watchlist}
          toggleWatch={toggleWatch}
        />
      );
    case "bigMoney":
      return (
        <BigMoneyPage datasets={datasets} />
      );
    case "chips":
      return (
        <ChipAnalysisPage datasets={datasets} />
      );
    case "watchlist":
      return (
        <WatchlistPage
          watchlist={watchlist}
          toggleWatch={toggleWatch}
          onNavigateToStock={onNavigateToStock}
        />
      );
    case "portfolio":
      return (
        <PortfolioPage
          datasets={datasets}
          portfolio={portfolio}
          setPortfolio={setPortfolio}
          onNavigateToStock={onNavigateToStock}
        />
      );
    case "alerts":
      return <AlertsPage />;
    case "goldenExit":
      return <GoldenExitPage datasets={datasets} portfolio={portfolio} onNavigateToStock={onNavigateToStock} />;
    case "news":
      return <GlobalNewsPage news={globalNews} />;
    case "learn":
      return <LearningPage />;
    default:
      return null;
  }
}

async function loadDataset(item: Omit<DatasetBox, "status" | "data">): Promise<{ status: DatasetStatus; data: Record<string, unknown> | null }> {
  const paths = [item.path, ...(item.fallbackPaths ?? [])];
  let sawError = false;

  for (const path of paths) {
    try {
      const res = await fetch(path, { cache: "default" });
      if (!res.ok || res.status === 404) continue;
      const contentType = res.headers.get("content-type");
      if (contentType && contentType.includes("text/html")) continue;
      try {
        const data = await res.json();
        return { status: "ready", data };
      } catch {
        sawError = true;
      }
    } catch {
      sawError = true;
    }
  }

  return { status: sawError ? "error" : "missing", data: null };
}

function App() {
  const [active, setActive] = useState<MenuKey>(initialView());
  const [datasets, setDatasets] = useState<Record<string, DatasetBox>>({});
  const [globalNews, setGlobalNews] = useState<GlobalNews[]>([]);
  const [selectedSector, setSelectedSector] = useState<string>("");
  const [stockId, setStockId] = useState(initialStockId());

  const [watchlist, setWatchlist] = useState<string[]>(() => {
    const saved = localStorage.getItem("tw_stock_watchlist");
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        return [];
      }
    }
    return [];
  });

  const [portfolio, setPortfolio] = useState<PortfolioItem[]>([]);
  const [portfolioLoaded, setPortfolioLoaded] = useState(false);

  useEffect(() => {
    fetch("http://localhost:3000/api/portfolio")
      .then(r => r.json())
      .then(data => {
        if (Array.isArray(data) && data.length > 0) {
          setPortfolio(data);
          // Sync to localStorage as backup
          localStorage.setItem("tw_stock_portfolio", JSON.stringify(data));
        } else {
          // Check localstorage for migration
          const saved = localStorage.getItem("tw_stock_portfolio");
          if (saved) {
            try {
              const parsed = JSON.parse(saved);
              if (Array.isArray(parsed) && parsed.length > 0) {
                setPortfolio(parsed);
                fetch("http://localhost:3000/api/portfolio", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(parsed)
                });
              }
            } catch (e) {}
          }
        }
        setPortfolioLoaded(true);
      })
      .catch((e) => {
        console.error("Failed to load portfolio from API", e);
        // Fallback to localstorage
        const saved = localStorage.getItem("tw_stock_portfolio");
        if (saved) {
          try {
            setPortfolio(JSON.parse(saved));
          } catch (e) {}
        }
        setPortfolioLoaded(true);
      });
  }, []);

  useEffect(() => {
    const next: Record<string, DatasetBox> = {};
    DATASETS.forEach((item) => {
      next[item.key] = { ...item, status: "loading", data: null };
    });
    setDatasets(next);

    DATASETS.forEach((item) => {
      loadDataset(item)
        .then(({ status, data }) => {
          setDatasets((prev) => ({ ...prev, [item.key]: { ...item, status, data } }));
          if (item.key === "watchlist" && status === "ready" && data && watchlist.length === 0) {
            const defaultRows = Array.isArray(data.records) ? data.records : Array.isArray(data.items) ? data.items : [];
            const defaultWatch = defaultRows.map(
              (r: any) => `${r.stock_code || r.stock_id} ${r.stock_name || ""}`.trim()
            );
            if (defaultWatch.length > 0) {
              setWatchlist(defaultWatch);
              localStorage.setItem("tw_stock_watchlist", JSON.stringify(defaultWatch));
            }
          }
        })
        .catch(() => {
          setDatasets((prev) => ({ ...prev, [item.key]: { ...item, status: "error", data: null } }));
        });
    });
  }, []);

  useEffect(() => {
    fetch("/data/global_news_latest.json", { cache: "default" })
      .then((res) => {
        if (!res.ok || res.status === 404) return null;
        const contentType = res.headers.get("content-type");
        if (contentType && contentType.includes("text/html")) return null;
        return res.json();
      })
      .then((data) => {
        const records = Array.isArray(data?.records) ? data.records : [];
        setGlobalNews(
          records
            .filter((row: GlobalNews) => row?.title && row?.link)
            .slice(0, 15)
        );
      })
      .catch(() => setGlobalNews([]));
  }, []);

  // 當今日的 recommendations 載入完成時，如果當前 stockId 為 "2330" 或為空，則自動代入今日評級第一的股票代碼 (保證預建 JSON 存在)
  useEffect(() => {
    if (datasets.recommendations?.status === "ready" && datasets.recommendations.data) {
      const recs = rows<StockRow>(datasets.recommendations.data, ["records", "items", "recommendations"]);
      if (recs.length > 0 && (stockId === "2330" || !stockId)) {
        const firstCode = recs[0].stock_code || recs[0].stock_id;
        if (firstCode) {
          setStockId(firstCode);
        }
      }
    }
  }, [datasets.recommendations, stockId]);

  const toggleWatch = (codeAndName: string) => {
    setWatchlist((prev) => {
      let next;
      if (prev.includes(codeAndName)) {
        next = prev.filter((x) => x !== codeAndName);
      } else {
        next = [...prev, codeAndName];
      }
      localStorage.setItem("tw_stock_watchlist", JSON.stringify(next));
      return next;
    });
  };

  const navigateToStock = (code: string) => {
    setStockId(code);
    setActive("stock");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const navigateToSector = (name: string) => {
    setSelectedSector(name);
    setActive("flow");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const sidebarSource = datasets.sectorRotation?.data ?? null;
  const sourceDate = getDate(sidebarSource) ?? "等待資料";
  const marketChange = getNumber(sidebarSource, ["market_chg_1d", "market_change_pct", "index_change_pct"]);

  return (
    <div className="alpha-app">
      <aside className="alpha-sidebar">
        <Brand />
        <nav className="alpha-nav">
          {MENU.map((item) => (
            <button
              className={active === item.key ? "active" : ""}
              key={item.key}
              type="button"
              onClick={() => setActive(item.key)}
            >
              <span>{item.label}</span>
              <small>{item.desc}</small>
            </button>
          ))}
        </nav>
        <MarketStatus date={sourceDate} marketChange={marketChange} />
      </aside>
      <main className="alpha-main">
        <TopBar active={active} datasets={datasets} />
        <PageRouter
          active={active}
          datasets={datasets}
          selectedSector={selectedSector}
          setSelectedSector={setSelectedSector}
          stockId={stockId}
          setStockId={setStockId}
          watchlist={watchlist}
          toggleWatch={toggleWatch}
          portfolio={portfolio}
          setPortfolio={setPortfolio}
          onNavigateToStock={navigateToStock}
          onNavigateToSector={navigateToSector}
          globalNews={globalNews}
        />
      </main>
    </div>
  );
}

function GlobalNewsPage({ news }: { news: GlobalNews[] }) {
  return (
    <section className="page-stack">
      <div className="section-header">
        <div>
          <h2>全球重點財經動態</h2>
          <p>彙整國內外市場新聞，作為盤勢與情緒因子的觀察入口。</p>
        </div>
        <div className={`dataset-badge ${news.length > 0 ? "ready" : "missing"}`}>
          <strong>{news.length > 0 ? "READY" : "WAITING"}</strong>
          <span>{news.length} 則新聞</span>
        </div>
      </div>
      {news.length === 0 ? (
        <div className="missing">
          <strong>目前沒有新聞快取</strong>
          <span>等待下一次盤後新聞更新。</span>
        </div>
      ) : (
        <div className="global-news-grid">
          {news.map((item, index) => (
            <a className="global-news-card" key={`${item.link}-${index}`} href={item.link} target="_blank" rel="noreferrer">
              <span>{formatNewsDate(item.pubDate)}</span>
              <strong>{item.title}</strong>
            </a>
          ))}
        </div>
      )}
    </section>
  );
}

function ChartsPage({
  datasets,
  onNavigateToStock,
  onNavigateToSector
}: {
  datasets: Record<string, DatasetBox>;
  onNavigateToStock: (code: string) => void;
  onNavigateToSector: (sectorName: string) => void;
}) {
  const rotation = datasets.sectorRotation;
  const sectors = rows<SectorRow>(rotation?.data, ["sectors", "records", "items"]);

  return (
    <section className="page-stack">
      <SectorChartsView
        dataset={rotation}
        sectors={sectors}
        datasets={datasets}
        onPickStock={onNavigateToStock}
        onPickSector={onNavigateToSector}
      />
    </section>
  );
}

function RotationDashboard({
  datasets,
  onNavigateToStock,
  onNavigateToSector
}: {
  datasets: Record<string, DatasetBox>;
  onNavigateToStock: (code: string) => void;
  onNavigateToSector: (sectorName: string) => void;
}) {
  const rotation = datasets.sectorRotation;
  const cp = datasets.cpRanking;
  const bottom = datasets.bottomFishing;
  const rec = datasets.recommendations;

  const sectors = rows<SectorRow>(rotation?.data, ["sectors", "records", "items"]);
  const cpRows = rows<SectorRow>(cp?.data, ["records", "items", "sectors"]);
  const bottomRows = rows<SectorRow>(bottom?.data, ["records", "items", "sectors"]);
  const recRows = rows<StockRow>(rec?.data, ["records", "items", "recommendations"]);
  const recV6Rows = rows<StockRow>(datasets.recommendationsV6?.data, ["records", "items", "recommendations"]);
  const [recTab, setRecTab] = useState<"v5" | "v6">("v5");

  return (
    <section className="page-stack">
      <HeroOverview dataset={rotation} sectors={sectors} />
      <MarketOverviewCard dataset={datasets.marketData} />
      <NightFuturesCard dataset={datasets.futuresAfterHours} />
      <div className="layout-3">
        <SectorTreemap
          dataset={rotation}
          sectors={sectors}
          datasets={datasets}
          onPickStock={onNavigateToStock}
          onPickSector={onNavigateToSector}
        />
        <RankingCard title="CP 值排行" dataset={cp} rows={cpRows} valueKey="cp_score" onPickSector={onNavigateToSector} />
        <RankingCard title="抄底偵測" dataset={bottom} rows={bottomRows} valueKey="bottom_score" onPickSector={onNavigateToSector} />
      </div>
      <div className="layout-1 single-focus">
        <div className="stock-recommendation panel">
          <div className="panel-header" style={{ marginBottom: "1rem", borderBottom: "1px solid var(--line)", paddingBottom: "1rem" }}>
            <h2 className="title">策略選股觀察</h2>
            <div className="tabs">
              <button className={`tab-btn ${recTab === "v5" ? "active" : ""}`} onClick={() => setRecTab("v5")}>
                V5 綜合強勢
              </button>
              <button className={`tab-btn ${recTab === "v6" ? "active" : ""}`} onClick={() => setRecTab("v6")}>
                V6 默默吃貨
              </button>
            </div>
          </div>
          {recTab === "v5" ? (
            <StockRecommendation title="" dataset={rec} rows={recRows} onPickStock={onNavigateToStock} meta="Alpha v5 / 情緒 / 量體過濾" />
          ) : (
            <StockRecommendation title="" dataset={datasets.recommendationsV6} rows={recV6Rows} onPickStock={onNavigateToStock} meta="Alpha v6 / 默默吃貨 / 低情緒 / 均線黏著" />
          )}
        </div>
      </div>
    </section>
  );
}

function FlowPage({
  datasets,
  selectedSector,
  setSelectedSector,
  onNavigateToStock
}: {
  datasets: Record<string, DatasetBox>;
  selectedSector: string;
  setSelectedSector: (value: string) => void;
  onNavigateToStock: (code: string) => void;
}) {
  const dataset = datasets.sectorRotation;
  const sectorRows = rows<SectorRow>(dataset?.data, ["sector_daily_flow", "sectors", "records"]);
  const [marketTab, setMarketTab] = useState("全部產業");

  const filteredSectors = useMemo(() => {
    if (marketTab === "全部產業") return sectorRows;
    return sectorRows.filter((row) => {
      const market = row.category || getSectorMarket(row.stocks, datasets.stockAlpha?.data);
      const isTwse = market === "TWSE";
      return marketTab === "上市" ? isTwse : !isTwse;
    });
  }, [sectorRows, marketTab, datasets.stockAlpha?.data]);

  const constituents = useMemo(() => {
    return sectorConstituentRows(selectedSector, datasets, dataset?.data);
  }, [selectedSector, datasets, dataset?.data]);

  return (
    <section className="page-stack">
      <SectionHeader title="資金流向" desc="展示 1 / 5 / 20 / 60 日法人淨買超，並拆分外資、投信、自營商貢獻。" dataset={dataset} />
      <TabBar items={["全部產業", "上市", "上櫃"]} active={marketTab} onChange={setMarketTab} />

      <div className="panel table-panel">
        <div className="section-title">
          <h3>產業板塊金流清單</h3>
          <span>點選板塊行可於下方展開成分股明細</span>
        </div>
        <div className="data-table" style={{ gridTemplateColumns: `repeat(7, minmax(110px, 1fr))` }}>
          <b>產業</b>
          <b>1日 (億)</b>
          <b>5日 (億)</b>
          <b>20日 (億)</b>
          <b>60日 (億)</b>
          <b>位置</b>
          <b>漲跌幅</b>
          {filteredSectors.slice(0, 40).map((row, i) => {
            const isSelected = row.sector_name === selectedSector;
            return (
              <div
                key={`${row.sector_name}-${i}`}
                style={{
                  display: "contents",
                  cursor: "pointer",
                }}
                onClick={() => setSelectedSector(row.sector_name)}
              >
                <span style={{ fontWeight: isSelected ? "bold" : "normal", color: isSelected ? "var(--accent)" : "inherit", background: isSelected ? "rgba(39,224,131,.08)" : "transparent" }}>
                  {row.sector_name}
                </span>
                <span style={{ color: getValColor(row.net_1d_yi), background: isSelected ? "rgba(39,224,131,.08)" : "transparent" }}>{fmtYi(row.net_1d_yi)}</span>
                <span style={{ color: getValColor(row.net_5d_yi), background: isSelected ? "rgba(39,224,131,.08)" : "transparent" }}>{fmtYi(row.net_5d_yi)}</span>
                <span style={{ color: getValColor(row.net_20d_yi), background: isSelected ? "rgba(39,224,131,.08)" : "transparent" }}>{fmtYi(row.net_20d_yi)}</span>
                <span style={{ color: getValColor(row.net_60d_yi), background: isSelected ? "rgba(39,224,131,.08)" : "transparent" }}>{fmtYi(row.net_60d_yi)}</span>
                <span style={{ background: isSelected ? "rgba(39,224,131,.08)" : "transparent" }}>{row.position !== undefined ? `${row.position}%` : "N/A"}</span>
                <span style={{ color: getValColor(row.chg_1d), background: isSelected ? "rgba(39,224,131,.08)" : "transparent" }}>{fmtPct(row.chg_1d)}</span>
              </div>
            );
          })}
        </div>
      </div>

      {selectedSector && (
        <div className="panel" style={{ borderLeft: "4px solid var(--accent)", animation: "fadeIn 0.3s ease" }}>
          <div className="section-title">
            <h3>【{selectedSector}】成分股明細</h3>
            <span>點擊股票代號可跳轉至「個股雷達」進行深度分析</span>
          </div>
          {constituents.length === 0 ? (
            <p style={{ color: "var(--muted)" }}>無成分股資料或未更新</p>
          ) : (
            <div className="data-table" style={{ gridTemplateColumns: `minmax(180px, 1.2fr) repeat(4, minmax(100px, 1fr))` }}>
              <b>股票代號與名稱</b>
              <b>板塊內排名</b>
              <b>最新股價</b>
              <b>1日漲跌幅</b>
              <b>1日淨買超 (億)</b>
              {constituents.map((stock, idx) => (
                <div key={`${stockCode(stock)}-${idx}`} style={{ display: "contents" }}>
                  <span
                    className="stock-label"
                    style={{ color: "var(--accent)", textDecoration: "underline", cursor: "pointer", fontWeight: "bold" }}
                    onClick={() => onNavigateToStock(stockCode(stock))}
                    title={stockLabel(stock)}
                  >
                    {stockLabel(stock)}
                  </span>
                  <span>#{stock.sector_rank || idx + 1}</span>
                  <span>{stock.close !== undefined ? fmtNumber(stock.close) : "-"}</span>
                  <span style={{ color: getValColor(stock.chg_1d ?? stock.change_pct) }}>{fmtPct(stock.chg_1d ?? stock.change_pct)}</span>
                  <span style={{ color: getValColor(stockNet1dYi(stock)) }}>{fmtYi(stockNet1dYi(stock))}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function StrengthPage({
  datasets,
  onNavigateToStock,
  onNavigateToSector
}: {
  datasets: Record<string, DatasetBox>;
  onNavigateToStock: (code: string) => void;
  onNavigateToSector: (sectorName: string) => void;
}) {
  const sector = datasets.sectorAlpha;
  const stock = datasets.stockAlpha;
  const sectorRows = rows<SectorRow>(sector?.data, ["records", "items", "sectors"]);
  const stockRows = rows<StockRow>(stock?.data, ["records", "items", "stocks"]);

  const [activeMetric, setActiveMetric] = useState("Alpha 分數");

  const sortedSectors = useMemo(() => {
    let list = [...sectorRows];
    if (activeMetric === "法人淨買超") {
      list.sort((a, b) => (b.net_5d_yi || 0) - (a.net_5d_yi || 0));
    }
    return list;
  }, [sectorRows, activeMetric]);

  const sortedStocks = useMemo(() => {
    let list = [...stockRows];
    if (activeMetric === "法人淨買超") {
      list.sort((a, b) => (b.net_1d_yi || 0) - (a.net_1d_yi || 0));
    } else if (activeMetric === "成交值放大") {
      list.sort((a, b) => (b.trade_value_yi || 0) - (a.trade_value_yi || 0));
    }
    return list;
  }, [stockRows, activeMetric]);

  return (
    <section className="page-stack">
      <SectionHeader title="強勢排行" desc="依 Sector Alpha v4、Stock Alpha v4、報酬率、相對強弱與基本面因子排序。" dataset={stock} />
      <TabBar
        items={["Alpha 分數", "法人淨買超", "成交值放大"]}
        active={activeMetric}
        onChange={setActiveMetric}
      />
      <div className="layout-2">
        <section className="panel">
          <SectionTitle title="Sector Alpha 排行" meta="點擊產業可看金流" />
          {sortedSectors.slice(0, 10).map((row, index) => {
            const name = row.sector_name || row.name || "";
            return (
              <div
                className="rank-row"
                key={`sector-alpha-${index}`}
                style={{ cursor: "pointer" }}
                onClick={() => onNavigateToSector(name)}
              >
                <span>{index + 1}</span>
                <strong>{name}</strong>
                <em style={{ color: "var(--accent)" }}>{fmtNumber(row.alpha_score ?? row.cp_score)}</em>
              </div>
            );
          })}
        </section>

        <section className="panel">
          <SectionTitle title="Stock Alpha v4 觀察清單" meta="點擊個股看價格/籌碼趨勢" />
          {sortedStocks.slice(0, 12).map((row, index) => {
            const code = row.stock_code || row.stock_id || "";
            return (
            <div
              className="stock-row"
              key={`stock-alpha-${index}`}
              style={{ cursor: "pointer" }}
              onClick={() => onNavigateToStock(code)}
            >
                <strong className="stock-label" title={stockLabel(row)}>{stockLabel(row)}</strong>
                <span>{row.sector_name || row.industry || "N/A"}</span>
                <em style={{ color: "var(--accent)" }}>{fmtNumber(row.stock_alpha_v4 ?? row.alpha_score, 1)}</em>
                <small>{row.reason || "三大法人金流匯入"}</small>
            </div>
            );
          })}
        </section>
      </div>
    </section>
  );
}

function IndustryMapPage({
  datasets,
  selectedSector,
  setSelectedSector,
  onNavigateToStock
}: {
  datasets: Record<string, DatasetBox>;
  selectedSector: string;
  setSelectedSector: (value: string) => void;
  onNavigateToStock: (code: string) => void;
}) {
  const dataset = datasets.sectorRotation;
  const sectors = rows<SectorRow>(dataset?.data, ["sectors", "records", "items"]);

  const constituents = useMemo(() => {
    return sectorConstituentRows(selectedSector, datasets, dataset?.data);
  }, [selectedSector, datasets, dataset?.data]);

  return (
    <section className="page-stack">
      <SectionHeader title="產業地圖" desc="呈現產業與子產業，面積代表成交值或市值，顏色代表資金淨流或報酬。" dataset={dataset} />
      <TabBar items={["法人淨買超", "CP 值", "抄底分數"]} active="法人淨買超" onChange={() => {}} />
      <div className="honeycomb-map">
        {sectors.slice(0, 40).map((sector, index) => {
          const name = sector.sector_name || sector.name || "";
          const isSelected = name === selectedSector;
          return (
            <button
              key={`${name}-${index}`}
              type="button"
              style={{
                borderColor: isSelected ? "var(--accent)" : "rgba(39,224,131,.22)",
                boxShadow: isSelected ? "0 0 16px rgba(39,224,131,.3)" : "none",
                background: isSelected ? "rgba(39,224,131,.18)" : "rgba(255,255,255,.035)"
              }}
              onClick={() => setSelectedSector(name)}
            >
              {name}
              <span>{fmtNumber(sector.net_1d_yi)} 億</span>
            </button>
          );
        })}
      </div>

      {selectedSector && (
        <div className="panel" style={{ borderLeft: "4px solid var(--accent)", marginTop: "14px" }}>
          <div className="section-title">
            <h3>【{selectedSector}】產業成分股地圖連動</h3>
            <span>點選個股可前往「個股雷達」檢視日線趨勢</span>
          </div>
          {constituents.length === 0 ? (
            <p style={{ color: "var(--muted)" }}>無成分股資料</p>
          ) : (
            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginTop: "10px" }}>
              {constituents.map((stock, i) => (
                <div
                  key={`${stockCode(stock)}-${i}`}
                  className="metric"
                  style={{ cursor: "pointer", minWidth: "140px", border: "1px solid rgba(255,255,255,0.08)" }}
                  onClick={() => onNavigateToStock(stockCode(stock))}
                >
                  <span className="stock-label" style={{ color: "var(--accent)", fontWeight: "bold" }} title={stockLabel(stock)}>{stockLabel(stock)}</span>
                  <div style={{ color: getValColor(stock.chg_1d ?? stock.change_pct), fontSize: "16px", fontWeight: "bold", marginTop: "5px" }}>
                    {fmtPct(stock.chg_1d ?? stock.change_pct)}
                  </div>
                  <small style={{ display: "block", marginTop: "4px" }}>金流：{fmtYi(stockNet1dYi(stock))}</small>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function EtfHoldingsPanel({
  dataset,
  holding,
  stockBasic,
  stockId
}: {
  dataset?: DatasetBox;
  holding?: EtfHoldingRow;
  stockBasic?: StockRow;
  stockId: string;
}) {
  const payloadStatus = String(dataset?.data?.status || "");
  const message = String(dataset?.data?.message || "");
  const constituents = holding?.constituents || [];
  const title = `ETF 成份股與權重 ${stockLabel(stockBasic || { stock_code: stockId })}`;

  if (dataset?.status !== "ready") {
    return <MissingAwarePanel dataset={dataset} title={title} />;
  }

  if (!holding || constituents.length === 0) {
    return (
      <div className="missing">
        <strong>{title}</strong>
        <span>{payloadStatus === "warning" ? message || "ETF 成份股資料尚未匯入。" : "目前找不到這檔 ETF 的成份股資料。"}</span>
      </div>
    );
  }

  return (
    <section className="panel">
      <SectionTitle
        title={title}
        meta={`${holding.as_of_date || "N/A"} · ${holding.holdings_count || constituents.length} 檔 · 權重覆蓋 ${fmtPct(holding.weight_coverage_pct)}`}
      />
      <div className="source-line">來源：{holding.source?.join("、") || "ETF holdings processed data"}</div>
      <div className="data-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>成份股</th>
              <th>權重</th>
              <th>股數</th>
              <th>市值</th>
            </tr>
          </thead>
          <tbody>
            {constituents.slice(0, 80).map((item) => (
              <tr key={`${item.stock_code || item.stock_id}-${item.weight_pct}`}>
                <td>{stockLabel({ stock_code: item.stock_code || item.stock_id, stock_name: item.stock_name })}</td>
                <td>{fmtPct(item.weight_pct)}</td>
                <td>{fmtNumber(item.shares)}</td>
                <td>{fmtYi(item.market_value_yi)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function StockRadarPage({
  datasets,
  stockId,
  setStockId,
  watchlist,
  toggleWatch
}: {
  datasets: Record<string, DatasetBox>;
  stockId: string;
  setStockId: (value: string) => void;
  watchlist: string[];
  toggleWatch: (codeAndName: string) => void;
}) {
  const stockDataset = datasets.stockAlpha;
  const stockBasic = useMemo(() => findStockBasic(datasets, stockId), [datasets, stockId]);
  const etfHolding = useMemo(() => findEtfHolding(datasets, stockId), [datasets, stockId]);
  const showEtfHoldings = isEtfCode(stockId) || stockBasic?.sector_name === "ETF" || stockBasic?.industry === "ETF";

  const [trendData, setTrendData] = useState<StockTrendPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // 動態抓取今日推薦的 10 檔股票代碼與名稱作為快捷按鈕 (保證預建趨勢存在)
  const availableTrendStocks = useMemo(() => {
    const recs = rows<StockRow>(datasets.recommendations?.data, ["records", "items", "recommendations"]);
    if (recs.length > 0) {
      return recs.slice(0, 10).map((r) => ({
        code: String(r.stock_code || r.stock_id || ""),
        name: String(r.stock_name || "")
      })).filter((s) => s.code);
    }
    // Fallback 到先前已生成的前幾檔
    return [
      { code: "1227", name: "福懋" },
      { code: "1736", name: "喬山" },
      { code: "2002", name: "中鋼" },
      { code: "2892", name: "第一金" }
    ];
  }, [datasets.recommendations?.data]);

  useEffect(() => {
    if (!stockId) return;
    setLoading(true);
    setLoadError(null);
    setTrendData(null);

    fetch(`/data/trends/${stockId}.json`, { cache: "default" })
      .then((res) => {
        if (!res.ok) {
          throw new Error(`此股票暫無歷史趨勢圖表資料`);
        }
        // 防止 Vite SPA 404 fallback 傳回 index.html (以 '<' 為開頭)
        const contentType = res.headers.get("content-type");
        if (contentType && !contentType.includes("application/json")) {
          throw new Error(`此股票暫無歷史趨勢圖表資料 (無 JSON)`);
        }
        return res.json();
      })
      .then((data) => {
        if (!data || typeof data !== "object") {
          throw new Error("格式不符合正確的 JSON 趨勢規範");
        }
        setTrendData(data);
        setLoading(false);
      })
      .catch((err) => {
        console.warn(err);
        setLoadError(err.message);
        setLoading(false);
      });
  }, [stockId]);

  const trendsPath = `/data/trends/${stockId || "1227"}.json`;
  const isWatched = watchlist.some((x) => x.startsWith(stockId));

  return (
    <section className="page-stack">
      <SectionHeader title="個股雷達" desc="包含收盤價格、均線走勢、法人三方買賣超、大戶動向與 Alpha 評估指標。" dataset={stockDataset} />

      {/* 動態渲染推薦資料中的股票作為快捷鈕 */}
      <div className="panel" style={{ display: "flex", flexWrap: "wrap", gap: "8px", padding: "12px" }}>
        <span style={{ color: "var(--muted)", alignSelf: "center" }}>今日推薦股趨勢快捷鈕：</span>
        {availableTrendStocks.map((stk) => (
          <button
            key={stk.code}
            type="button"
            className={`taste-action ${stockId === stk.code ? "active" : ""}`}
            style={{
              background: stockId === stk.code ? "var(--accent)" : "rgba(39,224,131,.08)",
              color: stockId === stk.code ? "#000" : "var(--accent)",
              border: "1px solid var(--accent)",
              borderRadius: "20px",
              padding: "4px 12px"
            }}
            onClick={() => setStockId(stk.code)}
          >
            {stk.code} {stk.name}
          </button>
        ))}
      </div>

      <div className="stock-search">
        <input
          value={stockId}
          onChange={(event) => setStockId(event.target.value.trim())}
          placeholder="輸入股票代號，例如 1227 或 2892"
          style={{ width: "260px" }}
        />
        {(trendData || stockBasic) && (
          <button
            type="button"
            style={{
              marginLeft: "10px",
              background: isWatched ? "var(--danger)" : "var(--accent)",
              color: "#000",
              border: "none",
              padding: "8px 16px"
            }}
            onClick={() => {
              const id = trendData ? trendData.stock_id : stockBasic!.stock_code;
              const name = trendData ? trendData.stock_name : (stockBasic!.stock_name || "");
              toggleWatch(`${id} ${name}`);
            }}
          >
            {isWatched ? "★ 移出觀察清單" : "☆ 加入觀察清單"}
          </button>
        )}
        <span style={{ marginLeft: "auto" }}>動態路徑：{trendsPath}</span>
      </div>

      {loading && <div className="panel">個股趨勢資料載入中...</div>}
      {loadError && stockBasic && (
        <div className="panel" style={{
          background: "rgba(251, 191, 36, 0.08)",
          borderLeft: "4px solid #fbbf24",
          color: "var(--text)",
          padding: "12px",
          marginBottom: "16px",
          borderRadius: "4px",
          fontSize: "14px",
          display: "flex",
          alignItems: "center",
          gap: "8px"
        }}>
          <span>⚠️</span>
          <span><strong>趨勢提示：</strong>{loadError}。已為您呈現今日行情報價，您仍可將此個股加入自選股中。</span>
        </div>
      )}
      {loadError && !stockBasic && (
        <div className="missing">
          <strong>無此個股資料</strong>
          <span>找不到股票代號 {stockId} 且無基本行情資料。</span>
        </div>
      )}

      {stockBasic && !trendData && !loading && (
        <div className="layout-3">
          <div className="metric">
            <span>個股 / 市場 / 產業</span>
            <strong>{stockLabel(stockBasic)}</strong>
            <small>{stockBasic.market || "N/A"} / {stockBasic.sector_name || stockBasic.industry || "未分類"}</small>
          </div>
          <div className="metric">
            <span>最新收盤</span>
            <strong>{fmtNumber(stockBasic.close)}</strong>
            <small>資料日期: {String((stockBasic as any).price_date || "盤後批次")}</small>
          </div>
          <div className="metric">
            <span>日漲跌</span>
            <strong style={{ color: getValColor(stockBasic.change_pct) }}>{fmtPct(stockBasic.change_pct)}</strong>
            <small>成交值 {fmtNumber(stockBasic.trade_value_yi)} 億</small>
          </div>
        </div>
      )}

      {showEtfHoldings && (
        <EtfHoldingsPanel
          dataset={datasets.etfHoldings}
          holding={etfHolding}
          stockBasic={stockBasic}
          stockId={stockId}
        />
      )}

      {trendData && !loading && (
        <>
          <div className="layout-3">
            <div className="metric">
              <span>個股 / 市場 / 產業</span>
              <strong>{trendData.stock_id} {trendData.stock_name}</strong>
              <small>{trendData.market} / {trendData.industry}</small>
            </div>
            <div className="metric">
              <span>最新價格</span>
              <strong>
                {trendData.price && trendData.price.length > 0
                  ? trendData.price[trendData.price.length - 1].close
                  : "N/A"}
              </strong>
              <small>更新時間: {trendData.generated_at.split("T")[0]}</small>
            </div>
            <div className="metric">
              <span>Alpha 評估得分</span>
              <strong>
                {trendData.alpha && trendData.alpha.length > 0
                  ? trendData.alpha[trendData.alpha.length - 1].alpha_score_total.toFixed(2)
                  : "N/A"}
              </strong>
              <small>多因子綜合評估</small>
            </div>
          </div>

          <div className="chart-grid">
            <div className="panel">
              <SectionTitle title="價格趨勢與日線均線" meta="折線：收盤價 (綠) / MA5 (黃) / MA20 (紫)" />
              <PriceLineChart data={trendData.price} />
            </div>

            <div className="panel">
              <SectionTitle title="三大法人買賣超流量" meta="直條：正數買超張數 (綠) / 負數賣超 (防守)" />
              <FlowBarChart data={trendData.institutional_flow} />
            </div>

            <div className="panel">
              <SectionTitle title="成交值與放大倍數" meta="折線：成交放大倍率 (1.0 表示持平)" />
              <ValueLineChart data={trendData.trade_value} />
            </div>

            <div className="panel">
              <SectionTitle title="多因子 Alpha 評級走勢" meta="指標：Stock Alpha 分數波動" />
              <AlphaLineChart data={trendData.alpha} />
            </div>
          </div>

          {trendData.recommendation && (
            <div className="panel" style={{ borderLeft: "4px solid var(--warn)" }}>
              <SectionTitle title="模型追蹤與評級建議" />
              <div className="layout-3" style={{ marginTop: "10px" }}>
                <Metric label="首次觀察日期" value={trendData.recommendation.first_recommend_date} />
                <Metric label="觀察時價格" value={String(trendData.recommendation.recommend_close)} />
                <Metric label="追蹤總報酬" value={fmtPct(trendData.recommendation.post_recommend_return)} />
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function PriceLineChart({ data }: { data?: TrendPricePoint[] }) {
  if (!data || data.length === 0) return <div style={{ height: "170px" }} />;

  const width = 500;
  const height = 180;
  const padding = 25;

  const closes = data.map((d) => d.close);
  const ma5s = data.map((d) => d.ma5);
  const ma20s = data.map((d) => d.ma20);
  const allVals = [...closes, ...ma5s, ...ma20s].filter((x) => x !== undefined && !isNaN(x));

  const minVal = Math.min(...allVals) * 0.98;
  const maxVal = Math.max(...allVals) * 1.02;
  const valRange = maxVal - minVal || 1;

  const points = data.map((d, index) => {
    const x = padding + (index / (data.length - 1)) * (width - padding * 2);
    const y = height - padding - ((d.close - minVal) / valRange) * (height - padding * 2);
    const y5 = height - padding - ((d.ma5 - minVal) / valRange) * (height - padding * 2);
    const y20 = height - padding - ((d.ma20 - minVal) / valRange) * (height - padding * 2);
    return { x, y, y5, y20, date: d.trade_date, val: d.close };
  });

  const pricePath = points.map((p) => `${p.x},${p.y}`).join(" ");
  const ma5Path = points.map((p) => `${p.x},${p.y5}`).join(" ");
  const ma20Path = points.map((p) => `${p.x},${p.y20}`).join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "180px", background: "rgba(0,0,0,0.2)" }}>
      <line x1={padding} y1={padding} x2={width - padding} y2={padding} stroke="rgba(255,255,255,0.05)" />
      <line x1={padding} y1={height / 2} x2={width - padding} y2={height / 2} stroke="rgba(255,255,255,0.05)" />
      <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="rgba(255,255,255,0.15)" />

      <text x={width - 5} y={padding + 4} fill="var(--muted)" fontSize="9" textAnchor="end">{maxVal.toFixed(1)}</text>
      <text x={width - 5} y={height / 2 + 4} fill="var(--muted)" fontSize="9" textAnchor="end">{((maxVal + minVal) / 2).toFixed(1)}</text>
      <text x={width - 5} y={height - padding + 4} fill="var(--muted)" fontSize="9" textAnchor="end">{minVal.toFixed(1)}</text>

      <polyline fill="none" stroke="#e4b125" strokeWidth="1.2" strokeDasharray="2,2" points={ma5Path} />
      <polyline fill="none" stroke="#b086ff" strokeWidth="1.2" strokeDasharray="3,2" points={ma20Path} />
      <polyline fill="none" stroke="var(--accent)" strokeWidth="2.2" points={pricePath} />

      {points.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r="3" fill="var(--accent)" stroke="#000" strokeWidth="1" />
          <text x={p.x} y={height - 6} fill="var(--muted)" fontSize="8" textAnchor="middle">
            {p.date.substring(5)}
          </text>
          <text x={p.x} y={p.y - 8} fill="#fff" fontSize="8" fontWeight="bold" textAnchor="middle">
            {p.val}
          </text>
        </g>
      ))}
    </svg>
  );
}

function FlowBarChart({ data }: { data?: TrendFlowPoint[] }) {
  if (!data || data.length === 0) return <div style={{ height: "170px" }} />;

  const width = 500;
  const height = 180;
  const padding = 25;

  const validFlows = data.filter((d) => d.foreign_net_shares !== null || d.trustee_net_shares !== null);
  if (validFlows.length === 0) {
    return <div style={{ color: "var(--muted)", padding: "40px", textAlign: "center" }}>無法人資料</div>;
  }

  const foreignVals = validFlows.map((d) => (d.foreign_net_shares || 0) / 1000);
  const trusteeVals = validFlows.map((d) => (d.trustee_net_shares || 0) / 1000);
  const maxAbs = Math.max(...[...foreignVals, ...trusteeVals].map(Math.abs)) || 1;

  const chartMax = maxAbs * 1.15;
  const barWidth = 14;
  const gap = 16;
  const zeroY = height / 2;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "180px", background: "rgba(0,0,0,0.2)" }}>
      <line x1={padding} y1={zeroY} x2={width - padding} y2={zeroY} stroke="rgba(255,255,255,0.3)" />

      {validFlows.slice(-8).map((d, index) => {
        const x = padding + index * (barWidth * 2 + gap) + 20;
        const foreignK = (d.foreign_net_shares || 0) / 1000;
        const trusteeK = (d.trustee_net_shares || 0) / 1000;

        const fHeight = (Math.abs(foreignK) / chartMax) * (height / 2 - padding);
        const fY = foreignK >= 0 ? zeroY - fHeight : zeroY;
        const fColor = foreignK >= 0 ? "var(--accent)" : "var(--danger)";

        const tHeight = (Math.abs(trusteeK) / chartMax) * (height / 2 - padding);
        const tY = trusteeK >= 0 ? zeroY - tHeight : zeroY;
        const tColor = trusteeK >= 0 ? "#5cbbf6" : "#fb7293";

        return (
          <g key={index}>
            <rect x={x} y={fY} width={barWidth} height={fHeight} fill={fColor} opacity="0.85" rx="2" />
            <rect x={x + barWidth + 2} y={tY} width={barWidth} height={tHeight} fill={tColor} opacity="0.85" rx="2" />
            <text x={x + barWidth} y={height - 6} fill="var(--muted)" fontSize="8" textAnchor="middle">
              {d.trade_date ? d.trade_date.substring(5) : "盤後"}
            </text>
            {Math.abs(foreignK) > 0.1 && (
              <text x={x + barWidth / 2} y={foreignK >= 0 ? fY - 3 : fY + fHeight + 8} fill="#fff" fontSize="7" textAnchor="middle">
                {foreignK > 0 ? `+${foreignK.toFixed(0)}` : foreignK.toFixed(0)}
              </text>
            )}
          </g>
        );
      })}

      <g transform={`translate(${width - 80}, 15)`}>
        <rect width="8" height="8" fill="var(--accent)" />
        <text x="12" y="8" fill="var(--muted)" fontSize="8">外資(千張)</text>
        <rect y="12" width="8" height="8" fill="#5cbbf6" />
        <text x="12" y="20" fill="var(--muted)" fontSize="8">投信(千張)</text>
      </g>
    </svg>
  );
}

function ValueLineChart({ data }: { data?: TrendValuePoint[] }) {
  if (!data || data.length === 0) return <div style={{ height: "170px" }} />;

  const width = 500;
  const height = 180;
  const padding = 25;

  const mults = data.map((d) => d.trade_value_multiple);
  const minVal = Math.max(0, Math.min(...mults) * 0.9);
  const maxVal = Math.max(...mults) * 1.1;
  const valRange = maxVal - minVal || 1;

  const points = data.map((d, index) => {
    const x = padding + (index / (data.length - 1)) * (width - padding * 2);
    const y = height - padding - ((d.trade_value_multiple - minVal) / valRange) * (height - padding * 2);
    return { x, y, date: d.trade_date, val: d.trade_value_multiple };
  });

  const path = points.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "180px", background: "rgba(0,0,0,0.2)" }}>
      <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="rgba(255,255,255,0.15)" />
      {minVal <= 1 && 1 <= maxVal && (
        <line
          x1={padding}
          y1={height - padding - ((1 - minVal) / valRange) * (height - padding * 2)}
          x2={width - padding}
          y2={height - padding - ((1 - minVal) / valRange) * (height - padding * 2)}
          stroke="rgba(255,255,255,0.2)"
          strokeDasharray="4,4"
        />
      )}
      <polyline fill="none" stroke="#27e083" strokeWidth="2" points={path} />
      {points.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r="3" fill="#27e083" />
          <text x={p.x} y={height - 6} fill="var(--muted)" fontSize="8" textAnchor="middle">
            {p.date.substring(5)}
          </text>
          <text x={p.x} y={p.y - 6} fill="#fff" fontSize="8" textAnchor="middle">
            {p.val.toFixed(1)}x
          </text>
        </g>
      ))}
    </svg>
  );
}

function AlphaLineChart({ data }: { data?: TrendAlphaPoint[] }) {
  if (!data || data.length === 0) return <div style={{ height: "170px" }} />;

  const width = 500;
  const height = 180;
  const padding = 25;

  const alphas = data.map((d) => d.alpha_score_total);
  const minVal = Math.min(...alphas) * 0.95;
  const maxVal = Math.max(...alphas) * 1.05;
  const valRange = maxVal - minVal || 1;

  const points = data.map((d, index) => {
    const x = padding + (index / (data.length - 1)) * (width - padding * 2);
    const y = height - padding - ((d.alpha_score_total - minVal) / valRange) * (height - padding * 2);
    return { x, y, date: d.trade_date, val: d.alpha_score_total };
  });

  const path = points.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "180px", background: "rgba(0,0,0,0.2)" }}>
      <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="rgba(255,255,255,0.15)" />
      <polyline fill="none" stroke="#b086ff" strokeWidth="2" points={path} />
      {points.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r="3" fill="#b086ff" />
          <text x={p.x} y={height - 6} fill="var(--muted)" fontSize="8" textAnchor="middle">
            {p.date.substring(5)}
          </text>
          <text x={p.x} y={p.y - 6} fill="#fff" fontSize="8" textAnchor="middle">
            {p.val.toFixed(1)}
          </text>
        </g>
      ))}
    </svg>
  );
}

function BigMoneyPage({ datasets }: { datasets: Record<string, DatasetBox> }) {
  const dataset = datasets.futuresAfterHours;
  if (dataset?.status !== "ready") return <MissingAwarePanel dataset={dataset} title="台指期夜盤指數" />;

  const latest = (dataset.data?.latest || {}) as Record<string, any>;
  const records = rows<Record<string, any>>(dataset.data, ["records"]);

  return (
    <section className="page-stack">
      <SectionHeader title="大戶動向" desc="統合法人買賣超、主力資金 Proxy、分點、融資融券與台指期夜盤。" dataset={dataset} />
      <div className="layout-2">
        <section className="panel night-futures-card">
          <SectionTitle title="台指期夜盤指數" meta="TX after_market" />
          <div className="night-futures-grid">
            <Metric label="夜盤指數" value={fmtNumber(latest.night_index || latest.settlement_price || latest.close)} />
            <Metric label="漲跌" value={fmtNumber(latest.spread)} val={latest.spread} />
            <Metric label="漲跌幅" value={fmtPct(latest.spread_per)} val={latest.spread_per} />
            <Metric label="成交量" value={fmtNumber(latest.volume)} />
            <Metric label="未沖銷量" value={fmtNumber(latest.open_interest)} />
            <Metric label="合約月份" value={String(latest.contract_date || "N/A")} />
          </div>

          {/* 以 SVG 繪製台指期夜盤指數趨勢，提供精準、無 Janky 感的視覺反饋 */}
          <div className="night-chart-svg" style={{ marginTop: "14px" }}>
            <FuturesSvgChart records={records} />
          </div>
          <div className="source-line" style={{ marginTop: "10px" }}>來源：{String(dataset.data?.source || "FinMind")} · 資料日期 {String(dataset.data?.as_of_date || "N/A")}</div>
        </section>

        <MissingAwarePanel dataset={datasets.sectorRotation} title="法人與主力 Proxy 排行" />
      </div>
    </section>
  );
}

// 繪製台指期夜盤趨勢的 SVG 折線圖元件
function FuturesSvgChart({ records }: { records: any[] }) {
  const data = records
    .slice(-30)
    .filter((r) => Number.isFinite(Number(r.night_index ?? r.close)));
  if (data.length === 0) return <div style={{ height: "132px" }} />;

  const width = 580;
  const height = 132;
  const padding = 15;

  const values = data.map((r) => Number(r.night_index ?? r.close)).filter(Number.isFinite);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const valRange = maxVal - minVal || 1;

  const xDenominator = Math.max(data.length - 1, 1);
  const points = data.map((d, index) => {
    const val = Number(d.night_index ?? d.close);
    const x = padding + (index / xDenominator) * (width - padding * 2);
    const y = height - padding - ((val - minVal) / valRange) * (height - padding * 2);
    return { x, y, val, date: d.date };
  });

  const path = points.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "132px", background: "rgba(0,0,0,0.3)", borderRadius: "10px", border: "1px solid var(--line)" }}>
      {/* 基準線與座標 */}
      <line x1={padding} y1={height / 2} x2={width - padding} y2={height / 2} stroke="rgba(255,255,255,0.05)" />
      <polyline fill="none" stroke="var(--accent)" strokeWidth="2.0" points={path} />

      {/* 終點閃爍節點 */}
      {points.length > 0 && (
        <circle cx={points[points.length - 1].x} cy={points[points.length - 1].y} r="4" fill="var(--accent)">
          <animate attributeName="r" values="3;6;3" dur="2s" repeatCount="indefinite" />
        </circle>
      )}

      {/* 首尾價格標籤 */}
      {points.length > 1 && (
        <>
          <text x={points[0].x} y={points[0].y - 6} fill="var(--muted)" fontSize="8">{points[0].val.toFixed(0)}</text>
          <text x={points[points.length - 1].x - 5} y={points[points.length - 1].y - 6} fill="var(--accent)" fontSize="9" fontWeight="bold" textAnchor="end">
            {points[points.length - 1].val.toFixed(0)}
          </text>
        </>
      )}
    </svg>
  );
}

function ChipAnalysisPage({ datasets }: { datasets: Record<string, DatasetBox> }) {
  const chipData = datasets.chipAnalysis;
  const records = rows<any>(chipData?.data, ["records", "items"]);

  return (
    <section className="page-stack">
      <SectionHeader title="籌碼分析" desc="融資餘額、融券餘額、借券餘額、外資持股比率與成交金流對照。" dataset={chipData} />

      {chipData?.status === "ready" ? (
        <div className="panel table-panel">
          <SectionTitle title="融資融券餘額明細" meta="最新籌碼水位走勢" />
          <div className="data-table" style={{ gridTemplateColumns: "repeat(6, 1fr)" }}>
            <b>交易日期</b>
            <b>股票代號與名稱</b>
            <b>融資餘額 (張)</b>
            <b>融券餘額 (張)</b>
            <b>融資使用率</b>
            <b>券資比</b>
            {records.slice(0, 30).map((r: any, idx: number) => (
              <div key={idx} style={{ display: "contents" }}>
                <span>{r.trade_date}</span>
                <span className="stock-label" style={{ color: "var(--accent)" }} title={stockLabel(r)}>{stockLabel(r)}</span>
                <span>{fmtNumber(r.margin_purchase_balance_shares, 0)}</span>
                <span>{fmtNumber(r.short_sale_balance_shares, 0)}</span>
                <span>{r.margin_purchase_limit_pct ? `${(r.margin_purchase_limit_pct * 100).toFixed(2)}%` : "N/A"}</span>
                <span>{r.short_sale_margin_purchase_ratio_pct ? `${(r.short_sale_margin_purchase_ratio_pct * 100).toFixed(2)}%` : "N/A"}</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="chart-grid">
          <MissingAwarePanel dataset={chipData} title="Margin Purchase Short Sale" />
          <ChartPlaceholder title="Securities Lending" />
        </div>
      )}
    </section>
  );
}

function WatchlistPage({
  watchlist,
  toggleWatch,
  onNavigateToStock
}: {
  watchlist: string[];
  toggleWatch: (codeAndName: string) => void;
  onNavigateToStock: (code: string) => void;
}) {
  return (
    <section className="page-stack">
      <div className="section-header">
        <div>
          <h2>自選監控</h2>
          <p>顯示自選產業與個股的價格、Alpha、資金淨流與風險狀態。</p>
        </div>
        <div className="dataset-badge ready">
          <strong>READY</strong>
          <span>本地快取</span>
        </div>
      </div>

      <div className="panel">
        <SectionTitle title="我的觀察清單" meta={`已加入 ${watchlist.length} 檔標的`} />
        {watchlist.length === 0 ? (
          <div className="missing">
            <strong>目前無觀察標的</strong>
            <span>您可以在「個股雷達」搜尋股票，並點選「加入觀察清單」按鈕，快速建立您的追蹤組合。</span>
          </div>
        ) : (
          <div className="data-table" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
            <b>股票代號與名稱</b>
            <b>操作連動</b>
            <b>移除自選</b>
            {watchlist.map((item, index) => {
              const code = item.split(" ")[0];
              return (
                <div key={index} style={{ display: "contents" }}>
                  <span style={{ fontWeight: "bold" }}>{item}</span>
                  <span>
                    <button
                      type="button"
                      className="taste-action"
                      onClick={() => onNavigateToStock(code)}
                      style={{ border: "1px solid var(--accent)", background: "transparent", color: "var(--accent)", padding: "2px 8px" }}
                    >
                      查看個股雷達 ➜
                    </button>
                  </span>
                  <span>
                    <button
                      type="button"
                      onClick={() => toggleWatch(item)}
                      style={{ background: "transparent", color: "var(--danger)", border: "none", cursor: "pointer" }}
                    >
                      ✕ 移出
                    </button>
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <RuleBuilder />
    </section>
  );
}

function AlertsPage() {
  return <StaticPage title="警示設定" desc="警示條件將保存在後端資料庫，需使用者隔離，不涉及自動下單。"><RuleBuilder /></StaticPage>;
}

function LearningPage() {
  return <StaticPage title="教學專區" desc="靜態內容，可使用 Markdown 或 CMS 編輯。"><div className="learning-grid"><GuideCard title="板塊圖怎麼看" /><GuideCard title="CP 值代表什麼" /><GuideCard title="抄底偵測風險" /><GuideCard title="資料來源說明" /></div></StaticPage>;
}

function Brand() {
  return <div className="brand"><div className="brand-logo">A</div><div><strong>台股 Alpha</strong><span>Capital Rotation</span></div></div>;
}

function MarketStatus({ date, marketChange }: { date: string; marketChange: number | null }) {
  const color = marketChange === null ? "inherit" : getValColor(marketChange);
  return <div className="market-status"><span>大盤漲跌</span><strong style={{ color }}>{marketChange === null ? "資料尚未更新" : fmtPct(marketChange)}</strong><small>資料日期 {date}</small></div>;
}

function TopBar({ active, datasets }: { active: MenuKey; datasets: Record<string, DatasetBox> }) {
  const [updateState, setUpdateState] = useState<{
    status: 'idle' | 'updating' | 'success' | 'error';
    progress: number;
    currentStep: string;
  }>({
    status: 'idle',
    progress: 0,
    currentStep: '準備就緒'
  });

  const ready = Object.values(datasets).filter((d) => d.status === "ready").length;
  const missing = Object.values(datasets).filter((d) => d.status === "missing").length;

  useEffect(() => {
    const syncStatus = async () => {
      try {
        const res = await fetch("http://localhost:3000/api/update-status");
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'updating' || data.status === 'success' || data.status === 'error') {
            setUpdateState({
              status: data.status,
              progress: data.progress,
              currentStep: data.currentStep || '同步中...'
            });
          }
        }
      } catch (e) {
        console.error("Failed to sync initial update status", e);
      }
    };
    syncStatus();
  }, []);

  useEffect(() => {
    let intervalId: any = null;

    if (updateState.status === 'updating') {
      intervalId = setInterval(async () => {
        try {
          const res = await fetch("http://localhost:3000/api/update-status");
          if (res.ok) {
            const data = await res.json();
            setUpdateState({
              status: data.status,
              progress: data.progress,
              currentStep: data.currentStep || '下載中...',
            });

            if (data.status === 'success') {
              clearInterval(intervalId);
              setTimeout(() => {
                window.location.reload();
              }, 2500);
            } else if (data.status === 'error') {
              clearInterval(intervalId);
            }
          }
        } catch (e) {
          console.error("Failed to fetch update status", e);
        }
      }, 1500);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [updateState.status]);

  const handleUpdate = async () => {
    if (!window.confirm("即將重新產生盤前/盤後批次快取，過程中您可以實時觀看更新進度。是否繼續？")) return;
    setUpdateState({ status: 'updating', progress: 5, currentStep: '準備啟動更新管線...' });
    try {
      const res = await fetch("http://localhost:3000/api/update", { method: "POST" });
      if (!res.ok) throw new Error("Failed to trigger update");
    } catch (e) {
      setUpdateState({
        status: 'error',
        progress: 0,
        currentStep: '啟動失敗，請確認後端伺服器 (node server.js) 是否執行中。'
      });
    }
  };

  const isUpdating = updateState.status === 'updating';

  return (
    <header className="topbar">
      <div className="topbar-title">
        <h1>{MENU.find((item) => item.key === active)?.label}</h1>
        <p>{MENU.find((item) => item.key === active)?.desc}</p>
      </div>
      <div className="topbar-meta" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <span className="topbar-stat"><strong>{ready}</strong> 份資料已載入</span>
        
        {/* Progress and status lightbar */}
        {(isUpdating || updateState.status === 'success' || updateState.status === 'error') ? (
          <div className="update-indicator-group">
            <div className="update-status-wrapper">
              <span className={`update-status-dot ${updateState.status}`} />
              <span>
                {updateState.status === 'updating' && '更新中'}
                {updateState.status === 'success' && '完成'}
                {updateState.status === 'error' && '異常'}
              </span>
            </div>
            <div className="update-progress-wrapper">
              <div className="update-progress-track">
                <div 
                  className={`update-progress-fill ${updateState.status === 'success' ? 'success' : updateState.status === 'error' ? 'error' : ''}`}
                  style={{ width: `${updateState.progress}%` }} 
                />
              </div>
              <span className="update-step-text" title={updateState.currentStep}>
                {updateState.currentStep}
              </span>
            </div>
          </div>
        ) : (
          <span className="topbar-stat is-muted"><strong>{missing}</strong> 份資料未更新</span>
        )}

        <button 
          className="topbar-refresh"
          onClick={handleUpdate} 
          disabled={isUpdating || updateState.status === 'success'}
        >
          {isUpdating ? `${updateState.progress}%` : "重新整理"}
        </button>
      </div>
    </header>
  );
}

function HeroOverview({ dataset, sectors }: { dataset?: DatasetBox; sectors: SectorRow[] }) {
  const leader = sectors[0];
  return (
    <section className="hero-card">
      {dataset?.status !== "ready" ? (
        <MissingState dataset={dataset} />
      ) : (
        <>
          <div className="hero-copy">
            <span className="eyebrow">Rotation Dashboard</span>
            <h2>{leader?.sector_name || leader?.name || "資金輪動"}<br />資金領跑</h2>
            <p>把市場狀態、資金方向、互動板塊圖、CP 值與抄底偵測收在同一個入口，作為盤後觀察與隔日功課。</p>
            <small>僅供觀察與研究，不構成投資建議。</small>
          </div>
          <div className="hero-metrics">
            <Metric label="1日買賣超" value={fmtYi(leader?.net_1d_yi)} />
            <Metric label="5日買賣超" value={fmtYi(leader?.net_5d_yi)} />
            <Metric label="20日買賣超" value={fmtYi(leader?.net_20d_yi)} />
            <Metric label="漲跌幅" value={fmtPct(leader?.chg_1d)} />
          </div>
        </>
      )}
    </section>
  );
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
        <Metric label="漲跌" value={fmtNumber(latest.spread)} val={latest.spread as number} />
        <Metric label="漲跌幅" value={fmtPct(latest.spread_per)} val={latest.spread_per as number} />
        <Metric label="成交量" value={fmtNumber(latest.volume)} />
        <Metric label="未沖銷量" value={fmtNumber(latest.open_interest)} />
        <Metric label="合約月份" value={String(latest.contract_date || "N/A")} />
      </div>
      <div className="night-chart-svg" style={{ marginTop: "14px" }}>
        <FuturesSvgChart records={records} />
      </div>
      <div className="source-line" style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
        <span>來源：{String(dataset.data?.source || "FinMind")} · 交易日(結算日) {String(dataset.data?.as_of_date || "N/A")}</span>
        <span style={{ color: "var(--warn)", opacity: 0.8 }}>
          (註: 週末前之夜盤歸屬為次一營業日)
        </span>
      </div>
    </section>
  );
}

function MarketOverviewCard({ dataset }: { dataset?: DatasetBox }) {
  if (dataset?.status !== "ready") return <MissingAwarePanel dataset={dataset} title="加權指數 (大盤)" />;
  
  const records = rows<Record<string, unknown>>(dataset.data, ["records"]);
  const taiex = records.find((r) => r.index_name === "TAIEX") || {};
  
  return (
    <section className="panel night-futures-card" style={{ marginBottom: "16px" }}>
      <SectionTitle title="加權指數 (大盤)" meta="TAIEX Overview" />
      <div className="night-futures-grid" style={{ marginBottom: 0 }}>
        <Metric label="大盤指數" value={fmtNumber(taiex.close)} />
        <Metric label="漲跌" value={fmtNumber(taiex.change)} val={taiex.change as number} />
        <Metric label="漲跌幅" value={fmtPct(taiex.change_pct)} val={taiex.change_pct as number} />
      </div>
      <div className="source-line" style={{ marginTop: "14px" }}>來源：TWSE · 資料日期 {String(taiex.trade_date || dataset.data?.as_of_date || "N/A")}</div>
    </section>
  );
}

function SectorTreemap({
  dataset,
  sectors,
  datasets,
  onPickStock,
  onPickSector
}: {
  dataset?: DatasetBox;
  sectors: SectorRow[];
  datasets: Record<string, DatasetBox>;
  onPickStock: (code: string) => void;
  onPickSector: (sectorName: string) => void;
}) {
  const [activeSector, setActiveSector] = useState("");
  const sectorTiles = useMemo(() => aggregateSectors(sectors).slice(0, 36), [sectors]);
  const stockTiles = useMemo(
    () => sectorConstituentRows(activeSector, datasets, dataset?.data).slice(0, 80),
    [activeSector, datasets, dataset?.data]
  );

  if (dataset?.status !== "ready") return <MissingAwarePanel dataset={dataset} title="可互動板塊圖" />;

  return (
    <section className="panel xl sector-treemap-panel">
      <div className="sector-treemap-head">
        <SectionTitle
          title={activeSector ? `【${activeSector}】成分股板塊圖` : "可互動板塊圖"}
          meta={activeSector ? `${stockTiles.length} 檔個股，點擊可進入個股雷達` : "面積代表資金/家數，顏色代表 1 日資金流向"}
        />
        {activeSector ? (
          <div className="sector-treemap-actions">
            <button type="button" onClick={() => setActiveSector("")}>返回全市場板塊</button>
            <button type="button" onClick={() => onPickSector(activeSector)}>查看資金流向</button>
          </div>
        ) : null}
      </div>

      {!activeSector ? (
        <div className="sector-treemap" role="list" aria-label="全市場產業板塊圖">
          {sectorTiles.map((sector, index) => {
            const name = sector.sector_name || sector.name || "";
            const flow = sector.net_1d_yi || 0;
            const span = sectorTileSpan(sector, index);
            const style: CSSProperties = {
              gridColumn: `span ${span.col}`,
              gridRow: `span ${span.row}`,
              background: flowBackground(flow),
            };
            return (
              <button
                className="treemap-tile sector-tile"
                key={`${name}-${index}`}
                type="button"
                style={style}
                onClick={() => setActiveSector(name)}
              >
                <strong>{name}</strong>
                <span>{fmtYi(flow)}</span>
                <small>{sector.stock_count || 0} 檔 · {fmtPct(sector.chg_1d)}</small>
              </button>
            );
          })}
        </div>
      ) : stockTiles.length === 0 ? (
        <div className="missing">
          <strong>無成分股資料</strong>
          <span>目前找不到 {activeSector} 的 `sector_constituents_latest.json` 或 fallback 成分股資料。</span>
        </div>
      ) : (
        <div className="sector-treemap stock-treemap" role="list" aria-label={`${activeSector} 成分股板塊圖`}>
          {stockTiles.map((stock, index) => {
            const code = stockCode(stock);
            const net1d = stockNet1dYi(stock);
            const span = stockTileSpan(stock, index);
            const style: CSSProperties = {
              gridColumn: `span ${span.col}`,
              gridRow: `span ${span.row}`,
              background: flowBackground(net1d || 0),
            };
            return (
              <button
                className="treemap-tile stock-tile"
                key={`${code}-${index}`}
                type="button"
                style={style}
                onClick={() => onPickStock(code)}
                title={stockLabel(stock)}
              >
                <strong className="stock-label">{stockLabel(stock)}</strong>
                <span className="tile-pct" style={{ color: getValColor(stock.chg_1d ?? stock.change_pct) }}>
                  {fmtPct(stock.chg_1d ?? stock.change_pct)}
                </span>
                <small>1日 {fmtYi(net1d)}</small>
                <small>5日 {fmtYi(stock.net_5d_yi)}</small>
                <small>20日 {fmtYi(stock.net_20d_yi)}</small>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}

function SectorChartsView({
  dataset,
  sectors,
  datasets,
  onPickStock,
  onPickSector
}: {
  dataset?: DatasetBox;
  sectors: SectorRow[];
  datasets: Record<string, DatasetBox>;
  onPickStock: (code: string) => void;
  onPickSector: (sectorName: string) => void;
}) {
  const [activeView, setActiveView] = useState<SectorChartView>("heatmap");
  const flowDataset = datasets.sectorFlowHistory;
  const flowPayload = flowDataset?.data as SectorFlowHistoryPayload | null | undefined;

  if (dataset?.status !== "ready") return <MissingAwarePanel dataset={dataset} title="資金熱力矩陣" />;

  return (
    <section className="panel xl sector-treemap-panel" style={{ display: "flex", flexDirection: "row", gap: "24px" }}>
      <div className="sector-chart-sidebar" style={{ width: "220px", flexShrink: 0, display: "flex", flexDirection: "column", gap: "16px", borderRight: "1px solid var(--line)", paddingRight: "20px" }}>
        <div className="sector-treemap-head">
          <SectionTitle
            title="資金圖表"
            meta="點擊產業進入個股資金流"
          />
        </div>

        <div className="vertical-tabs" role="tablist" aria-label="資金圖表視圖切換" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {SECTOR_CHART_TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={activeView === tab.key ? "active" : ""}
              onClick={() => setActiveView(tab.key)}
              style={{
                width: "100%",
                textAlign: "left",
                padding: "12px 16px",
                borderRadius: "8px",
                border: activeView === tab.key ? "1px solid var(--accent)" : "1px solid transparent",
                backgroundColor: activeView === tab.key ? "rgba(42, 252, 152, 0.05)" : "rgba(255, 255, 255, 0.03)",
                color: activeView === tab.key ? "var(--accent)" : "var(--text)",
                fontWeight: activeView === tab.key ? 600 : 400,
                cursor: "pointer",
                transition: "all 0.2s",
                fontSize: "15px"
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="sector-chart-content" style={{ flexGrow: 1, minWidth: 0, height: "650px" }}>
        {activeView === "heatmap" ? (
          <SectorFlowHeatmap dataset={flowDataset} payload={flowPayload} onPickSector={onPickSector} />
        ) : (
          <SectorFlowTrendLineChart dataset={flowDataset} payload={flowPayload} onPickSector={onPickSector} />
        )}
      </div>
    </section>
  );
}

function SectorFlowHeatmap({
  dataset,
  payload,
  onPickSector
}: {
  dataset?: DatasetBox;
  payload?: SectorFlowHistoryPayload | null;
  onPickSector?: (sector: string) => void;
}) {
  const rows = useMemo(() => sectorFlowHistoryRows(payload as Record<string, unknown>), [payload]);
  const dates = useMemo(() => recentFlowDates(rows, 15), [rows]);

  const heatmapSectors = useMemo(() => {
    if (!rows.length || !dates.length) return [];
    
    const dateSet = new Set(dates);
    const sectorStats = new Map<string, number>();
    
    rows.forEach(r => {
      if (dateSet.has(r.date)) {
        const current = sectorStats.get(r.sector) || 0;
        sectorStats.set(r.sector, current + Math.abs(r.total));
      }
    });

    const filtered = Array.from(sectorStats.entries())
      .filter(([name]) => name !== "未分類" && name !== "其他" && name !== "ETN" && name !== "REITs" && name !== "存託憑證(DR)")
      .sort((a, b) => b[1] - a[1]);
      
    return filtered.slice(0, 18).map(([name]) => name);
  }, [rows, dates]);

  const matrix = useMemo(() => {
    const map = new Map<string, Map<string, { total: number; foreign: number; trust: number; dealer: number }>>();
    rows.forEach(r => {
      let sectorMap = map.get(r.sector);
      if (!sectorMap) {
        sectorMap = new Map();
        map.set(r.sector, sectorMap);
      }
      sectorMap.set(r.date, { total: r.total, foreign: r.foreign, trust: r.trust, dealer: r.dealer });
    });
    return map;
  }, [rows]);

  const maxAbsVal = useMemo(() => {
    let maxVal = 1;
    heatmapSectors.forEach(sec => {
      const datesMap = matrix.get(sec);
      if (datesMap) {
        dates.forEach(d => {
          const val = datesMap.get(d)?.total || 0;
          if (Math.abs(val) > maxVal) {
            maxVal = Math.abs(val);
          }
        });
      }
    });
    return maxVal;
  }, [heatmapSectors, dates, matrix]);

  const [hoveredCell, setHoveredCell] = useState<{
    sector: string;
    date: string;
    total: number;
    foreign: number;
    trust: number;
    dealer: number;
    x: number;
    y: number;
  } | null>(null);

  if (dataset?.status !== "ready" || rows.length === 0 || !dates.length) {
    return <MissingAwarePanel dataset={dataset} title="資金熱力矩陣" />;
  }

  return (
    <div className="sector-chart-view sector-heatmap-panel" style={{ height: "100%", display: "flex", flexDirection: "column", gap: "12px", overflow: "hidden" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
        <div style={{ fontSize: "13px", color: "var(--muted)", display: "flex", alignItems: "center", gap: "16px" }}>
          <span>💡 橫軸為交易日 (近15日)，縱軸為核心熱門產業 (千股/張) · 點選查看明細</span>
          <span style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ display: "inline-block", width: "12px", height: "12px", borderRadius: "2px", backgroundColor: "rgba(39, 224, 131, 0.7)" }}></span>
              買超流入
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ display: "inline-block", width: "12px", height: "12px", borderRadius: "2px", backgroundColor: "rgba(235, 56, 76, 0.7)" }}></span>
              賣超流出
            </span>
          </span>
        </div>
      </div>

      <div style={{ flexGrow: 1, overflow: "auto", position: "relative" }} className="heatmap-scroll-container">
        <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: "3px", tableLayout: "fixed" }}>
          <thead>
            <tr>
              <th style={{ width: "120px", textAlign: "left", fontSize: "12px", padding: "8px 6px", color: "var(--muted)", fontWeight: 600, position: "sticky", left: 0, backgroundColor: "#0b100e", zIndex: 10 }}>產業名稱</th>
              {dates.map(d => (
                <th key={d} style={{ fontSize: "11px", textAlign: "center", padding: "6px", color: "var(--text)", opacity: 0.85, fontWeight: 500 }}>
                  {d.slice(5).replace("-", "/")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {heatmapSectors.map(sec => {
              const datesMap = matrix.get(sec);
              return (
                <tr key={sec}>
                  <td
                    onClick={() => onPickSector?.(sec)}
                    style={{
                      padding: "8px 6px",
                      fontSize: "13px",
                      fontWeight: 600,
                      color: "var(--accent)",
                      cursor: "pointer",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      position: "sticky",
                      left: 0,
                      backgroundColor: "#0b100e",
                      zIndex: 8,
                      borderRight: "1px solid var(--line)"
                    }}
                    title={`點選查看 ${sec} 明細`}
                  >
                    {sec}
                  </td>
                  {dates.map(d => {
                    const data = datesMap?.get(d) || { total: 0, foreign: 0, trust: 0, dealer: 0 };
                    const val = data.total;
                    const isUp = val >= 0;
                    
                    const ratio = Math.abs(val) / maxAbsVal;
                    const alpha = val === 0 ? 0.03 : 0.15 + ratio * 0.7;
                    
                    const bgColor = val === 0 
                      ? "rgba(255,255,255,0.03)" 
                      : isUp 
                        ? `rgba(39, 224, 131, ${alpha})` 
                        : `rgba(235, 56, 76, ${alpha})`;
                        
                    const textColor = val === 0
                      ? "rgba(255,255,255,0.15)"
                      : alpha > 0.45
                        ? "#000000"
                        : "#ffffff";

                    return (
                      <td
                        key={d}
                        onMouseEnter={(e) => {
                          const rect = e.currentTarget.getBoundingClientRect();
                          setHoveredCell({
                            sector: sec,
                            date: d,
                            ...data,
                            x: rect.left + rect.width / 2,
                            y: rect.top - 10
                          });
                        }}
                        onMouseLeave={() => setHoveredCell(null)}
                        onClick={() => onPickSector?.(sec)}
                        style={{
                          backgroundColor: bgColor,
                          borderRadius: "4px",
                          height: "36px",
                          textAlign: "center",
                          verticalAlign: "middle",
                          fontSize: "11px",
                          fontWeight: 700,
                          cursor: "pointer",
                          color: textColor,
                          transition: "all 0.15s ease",
                        }}
                        className="heatmap-cell"
                      >
                        {val === 0 ? "-" : `${isUp ? "+" : ""}${compactShares(val)}`}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {hoveredCell && createPortal(
        <div
          style={{
            position: "fixed",
            left: `${hoveredCell.x}px`,
            top: `${hoveredCell.y}px`,
            transform: "translate(-50%, -100%)",
            backgroundColor: "rgba(11, 16, 14, 0.95)",
            border: "1px solid rgba(255, 255, 255, 0.15)",
            borderRadius: "8px",
            padding: "10px 14px",
            zIndex: 10000,
            fontSize: "12px",
            backdropFilter: "blur(8px)",
            boxShadow: "0 10px 25px -5px rgba(0,0,0,0.5)",
            pointerEvents: "none",
            color: "#f5f8f2",
            lineHeight: "1.6"
          }}
        >
          <div style={{ fontWeight: 700, borderBottom: "1px solid var(--line)", paddingBottom: "4px", marginBottom: "6px" }}>
            {hoveredCell.sector} ({hoveredCell.date})
          </div>
          <div>外資：<span style={{ color: hoveredCell.foreign >= 0 ? "var(--color-down)" : "var(--color-up)" }}>{hoveredCell.foreign >= 0 ? "+" : ""}{compactShares(hoveredCell.foreign)}</span></div>
          <div>投信：<span style={{ color: hoveredCell.trust >= 0 ? "var(--color-down)" : "var(--color-up)" }}>{hoveredCell.trust >= 0 ? "+" : ""}{compactShares(hoveredCell.trust)}</span></div>
          <div>自營商：<span style={{ color: hoveredCell.dealer >= 0 ? "var(--color-down)" : "var(--color-up)" }}>{hoveredCell.dealer >= 0 ? "+" : ""}{compactShares(hoveredCell.dealer)}</span></div>
          <div style={{ marginTop: "4px", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "4px", fontWeight: 600 }}>
            合計：<span style={{ color: hoveredCell.total >= 0 ? "var(--color-down)" : "var(--color-up)" }}>{hoveredCell.total >= 0 ? "+" : ""}{compactShares(hoveredCell.total)}</span>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}

function SectorFlowTrendLineChart({
  dataset,
  payload,
  onPickSector
}: {
  dataset?: DatasetBox;
  payload?: SectorFlowHistoryPayload | null;
  onPickSector?: (sector: string) => void;
}) {
  const [metric, setMetric] = useState<"total" | "foreign" | "trust" | "dealer">("total");
  const rows = useMemo(() => sectorFlowHistoryRows(payload as Record<string, unknown>), [payload]);
  const dates = useMemo(() => recentFlowDates(rows, 20), [rows]);

  const topSectors = useMemo(() => {
    if (!rows.length || !dates.length) return [];
    const latestDate = dates[dates.length - 1];
    
    const latestFlows = rows
      .filter(r => r.date === latestDate && r.sector !== "未分類" && r.sector !== "其他" && r.sector !== "ETF")
      .map(r => ({ sector: r.sector, absVal: Math.abs(r[metric]) }))
      .sort((a, b) => b.absVal - a.absVal);

    return latestFlows.slice(0, 8).map(x => x.sector);
  }, [rows, dates, metric]);

  const chartData = useMemo(() => {
    if (!dates.length || !topSectors.length) return [];
    return dates.map(d => {
      const point: Record<string, any> = { date: d.slice(5).replace("-", "/") };
      topSectors.forEach(sec => {
        const found = rows.find(r => r.date === d && r.sector === sec);
        point[sec] = found ? found[metric] : null;
      });
      return point;
    });
  }, [rows, dates, topSectors, metric]);

  if (dataset?.status !== "ready" || rows.length === 0 || !dates.length) {
    return <MissingAwarePanel dataset={dataset} title="產業流量趨勢" />;
  }

  const COLORS = ["#27e083", "#5ad0ff", "#e4b125", "#ff8a5c", "#b58cff", "#ff6b8b", "#00d2d3", "#ff9f43"];

  return (
    <div className="sector-chart-view sector-trend-chart" style={{ height: "100%", display: "flex", flexDirection: "column", gap: "16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: "13px", color: "var(--muted)" }}>
          💡 顯示最新交易日法人進出量最高的前 8 大熱門產業趋势 (千股/張)
        </div>
        <div className="planet-controls" style={{ margin: 0, display: "flex", gap: "6px" }}>
          {[
            ["total", "三大法人合計"],
            ["foreign", "外資"],
            ["trust", "投信"],
            ["dealer", "自營商"]
          ].map(([key, label]) => (
            <button
              key={key}
              className={metric === key ? "active" : ""}
              type="button"
              onClick={() => setMetric(key as any)}
              style={{
                fontSize: "12px",
                padding: "6px 12px",
                borderRadius: "6px",
                border: metric === key ? "1px solid var(--accent)" : "1px solid transparent",
                backgroundColor: metric === key ? "rgba(42, 252, 152, 0.08)" : "rgba(255, 255, 255, 0.03)",
                color: metric === key ? "var(--accent)" : "var(--text)",
                cursor: "pointer",
                transition: "all 0.2s"
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flexGrow: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height="90%">
          <LineChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
            <CartesianGrid stroke="rgba(255,255,255,.05)" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" tick={{ fill: "rgba(232,242,234,.5)", fontSize: 11 }} axisLine={{ stroke: "rgba(255,255,255,.08)" }} tickLine={false} />
            <YAxis tick={{ fill: "rgba(232,242,234,.5)", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(value) => `${value >= 0 ? "+" : ""}${compactShares(value)}`} />
            <Tooltip
              contentStyle={{ border: "1px solid rgba(255,255,255,.1)", borderRadius: 8, background: "#070c0a", color: "#f5f8f2", fontSize: "12px" }}
              formatter={(value, name) => [`${Number(value) >= 0 ? "+" : ""}${compactShares(Number(value))}`, String(name)]}
              labelFormatter={(label) => `交易日期: ${label}`}
            />
            <Legend verticalAlign="bottom" height={36} iconType="circle" wrapperStyle={{ fontSize: "12px", color: "var(--text)" }} />
            {topSectors.map((sector, index) => (
              <Line
                key={sector}
                type="monotone"
                dataKey={sector}
                stroke={COLORS[index % COLORS.length]}
                strokeWidth={2}
                dot={{ r: 2, strokeWidth: 1 }}
                activeDot={{ r: 5 }}
                connectNulls
                onClick={() => onPickSector?.(sector)}
                style={{ cursor: "pointer" }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function sectorTileSpan(sector: SectorRow, index: number): { col: number; row: number } {
  const weight = Math.max(Math.abs(sector.net_1d_yi || 0), sector.trade_value_yi ? sector.trade_value_yi / 10 : 0, sector.stock_count || 0);
  if (index < 3 || weight >= 80) return { col: 3, row: 2 };
  if (index < 10 || weight >= 35) return { col: 2, row: 2 };
  return { col: 1, row: 1 };
}

function stockTileSpan(stock: StockRow, index: number): { col: number; row: number } {
  const weight = Math.max(Math.abs(stockNet1dYi(stock) || 0), stock.trade_value_yi || 0, stock.trade_value_twd ? stock.trade_value_twd / 100000000 : 0);
  if (index < 2 || weight >= 8) return { col: 3, row: 2 };
  if (index < 8 || weight >= 2) return { col: 2, row: 2 };
  return { col: 1, row: 1 };
}

function flowBackground(value: number): string {
  const strength = Math.min(Math.abs(value) / 40, 1);
  if (value > 0) {
    return `linear-gradient(135deg, rgba(216,90,48,${0.22 + strength * 0.42}), rgba(20,10,8,.92))`;
  }
  if (value < 0) {
    return `linear-gradient(135deg, rgba(39,224,131,${0.2 + strength * 0.36}), rgba(5,13,9,.92))`;
  }
  return "linear-gradient(135deg, rgba(255,255,255,.08), rgba(9,13,11,.92))";
}

function RankingCard({ title, dataset, rows, valueKey, onPickSector }: { title: string; dataset?: DatasetBox; rows: SectorRow[]; valueKey: keyof SectorRow; onPickSector: (name: string) => void }) {
  if (dataset?.status !== "ready") return <MissingAwarePanel dataset={dataset} title={title} />;
  return (
    <section className="panel">
      <SectionTitle title={title} meta={`${dataset?.label} (點選查看)`} />
      {rows.slice(0, 8).map((row, index) => {
        const sectorName = row.sector_name || row.name || "";
        return (
          <motion.div
            className="rank-row"
            key={`${title}-${index}`}
            style={{ cursor: "pointer", borderRadius: "8px", padding: "11px 8px" }}
            onClick={() => onPickSector(sectorName)}
            whileHover={{ scale: 1.01, backgroundColor: 'rgba(255,255,255,0.03)' }}
            whileTap={{ scale: 0.98 }}
          >
            <span>{index + 1}</span>
            <strong>{sectorName}</strong>
            <em style={{ color: "var(--accent)" }}>{fmtNumber(row[valueKey] as number | undefined)}</em>
          </motion.div>
        );
      })}
    </section>
  );
}

function StockRecommendation({ title = "今日觀察標的 Top 10", dataset, rows, onPickStock, meta = "Alpha v5 / 情緒 / 量體濾網" }: { title?: string; dataset?: DatasetBox; rows: StockRow[]; onPickStock: (code: string) => void; meta?: string }) {
  if (dataset?.status !== "ready") return <MissingAwarePanel dataset={dataset} title={title} />;
  return (
    <section className="panel">
      <SectionTitle title={title} meta={meta} />
      {rows.slice(0, 10).map((row, index) => {
        const code = row.stock_code || row.stock_id || "";
        const tags = row.tags || [];
        const score = row.Alpha_Score_v6 ?? row.Alpha_Score_v5 ?? row.stock_alpha_v5 ?? row.stock_alpha_v4 ?? row.alpha_score;
        const changePct = row.change_pct as number | undefined;
        const priceColor = changePct === undefined ? "inherit" : changePct > 0 ? "#eb384c" : changePct < 0 ? "#27e083" : "inherit";
        return (
          <motion.div
            className="stock-row recommendation-row"
            key={`${title}-${index}`}
            style={{ cursor: "pointer", borderRadius: "8px", padding: "11px 8px" }}
            onClick={() => onPickStock(code)}
            whileHover={{ scale: 1.01, backgroundColor: 'rgba(255,255,255,0.03)' }}
            whileTap={{ scale: 0.98 }}
          >
            <strong className="stock-label" title={stockLabel(row)}>{stockLabel(row)}</strong>
            <span>{row.sector_name || row.industry || "N/A"}</span>
            <em style={{ color: "var(--accent)" }}>{fmtNumber(score, 1)}</em>
            <small>
              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", fontSize: "12px" }}>
                <span style={{ color: "var(--text)" }}>成交 {fmtNumber(row.close)}</span>
                <span style={{ color: priceColor }}>
                  漲跌 {changePct !== undefined && changePct > 0 ? "+" : ""}{fmtNumber(changePct, 2)}%
                </span>
                <span style={{ color: "var(--muted)" }}>法人1日 {fmtNumber(row.net_1d_yi, 2)}億</span>
                <span style={{ color: "var(--muted)" }}>法人5日 {fmtNumber(row.net_5d_yi, 2)}億</span>
                <span className="sentiment-meter">情緒 {fmtNumber(row.sentiment_temperature, 0)}</span>
              </div>
              <span className="tag-list">
                {tags.slice(0, 4).map((tag) => (
                  <b key={`${code}-${tag}`}>{tag}</b>
                ))}
              </span>
              <span>{row.reason || (row.Vol_20d ? `20日均量 ${fmtNumber(row.Vol_20d, 0)} 張` : "資料管線預計算")}</span>
            </small>
          </motion.div>
        );
      })}
    </section>
  );
}

function SectionHeader({ title, desc, dataset }: { title: string; desc: string; dataset?: DatasetBox }) {
  return <section className="section-header"><div><h2>{title}</h2><p>{desc}</p></div><DatasetBadge dataset={dataset} /></section>;
}

function SectionTitle({ title, meta }: { title: string; meta?: string }) {
  return <div className="section-title"><h3>{title}</h3>{meta ? <span>{meta}</span> : null}</div>;
}

function Metric({ label, value, val }: { label: string; value: string; val?: number }) {
  let color = "inherit";
  if (val !== undefined) {
    color = getValColor(val);
  } else {
    if (value.startsWith("+")) color = "var(--danger)";
    if (value.startsWith("-")) color = "var(--accent)";
  }
  return <div className="metric"><span>{label}</span><strong style={{ color }}>{value}</strong></div>;
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
          <strong className="stock-label">
            {row.stock_code || row.stock_id ? stockLabel(row) : String(row.sector_name || row.stock_name || row.name || "N/A")}
          </strong>
          <em style={{ color: "var(--accent)" }}>{formatCell(row.net_1d_yi ?? row.stock_alpha_v4 ?? row.alpha_score ?? row.cp_score ?? row.bottom_score)}</em>
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

function fmtNumber(value: unknown, precision: number = 2): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "N/A";
  return value.toFixed(precision);
}

// 淨買超值格式化，改用更顯眼的萬張/億格式
function fmtYi(value: unknown): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)} 億`;
}

function fmtPct(value: unknown): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatCell(value: unknown): string {
  if (typeof value === "number") return value.toFixed(2);
  if (Array.isArray(value)) return value.join(", ");
  if (value === null || value === undefined) return "N/A";
  return String(value);
}

function getValColor(value: unknown): string {
  if (typeof value !== "number") return "inherit";
  if (value > 0) return "var(--danger)";
  if (value < 0) return "var(--accent)";
  return "inherit";
}

function initialView(): MenuKey {
  const path = window.location.pathname;
  if (path.startsWith("/stock/")) return "stock";
  const route = path.replace(/^\//, "").split("/")[0] as MenuKey;
  if (MENU.some((item) => item.key === route)) return route;
  return "rotation";
}

function initialStockId(): string {
  const match = window.location.pathname.match(/\/stock\/([^/]+)/);
  // 改為空，由 App 載入今日首選觀察股
  return match?.[1] || "";
}

function GoldenExitPage({ 
  datasets, 
  portfolio, 
  onNavigateToStock 
}: { 
  datasets: Record<string, DatasetBox>; 
  portfolio: any[]; 
  onNavigateToStock: (id: string) => void 
}) {
  const payload = datasets.goldenExit?.data;
  const status = datasets.goldenExit?.status;

  const [filterByPortfolio, setFilterByPortfolio] = useState(true);

  if (status === "loading") return <div className="panel" style={{ padding: "24px" }}>載入中...</div>;
  if (!payload || status === "error") return <div className="panel" style={{ padding: "24px" }}>無資料或尚未產生「黃金逃頂」分析。</div>;

  const allRecords = Array.isArray(payload.records) ? payload.records : [];
  
  // 篩選持股
  const portfolioIds = new Set((portfolio || []).map((p: any) => String(p.id)));
  const records = allRecords.filter((r: any) => {
    if (!filterByPortfolio) return true;
    return portfolioIds.has(String(r.stock_id));
  });

  const getDecision = (r: any) => {
    const close = r.close ?? 0;
    const defense = r.swing_defense ?? 0;
    const short_defense = r.chandelier_exit_short ?? parseFloat((defense * 1.05).toFixed(2));
    const support_1 = r.support_1 ?? parseFloat((close * 0.95).toFixed(2));
    const resistance_1 = r.resistance_1 ?? parseFloat((close * 1.05).toFixed(2));

    if (close <= defense) {
      return {
        type: "sell",
        label: "避險逃頂",
        action: "🔴 避險賣出",
        badgeClass: "decision-badge sell",
        timing: "明日開盤以市價或防守價附近波段減碼避險。",
        price: `跌破防守價 ${defense} 元`
      };
    } else if (close >= short_defense) {
      return {
        type: "buy",
        label: "強勢突破",
        action: "🟢 強勢買進",
        badgeClass: "decision-badge buy",
        timing: "明日開盤強勢跟進，或盤中回檔量縮買進。",
        price: `站上突破價 ${short_defense} 元`
      };
    } else {
      return {
        type: "hold",
        label: "波段持有",
        action: "🟡 波段持有",
        badgeClass: "decision-badge hold",
        timing: "多頭結構良好，波段續抱並以防守線為依據。",
        price: `支撐 ${support_1} 元 / 防守 ${defense} 元`
      };
    }
  };

  const renderPriceRangeBar = (r: any) => {
    const close = r.close ?? 0;
    const support = r.support_1 ?? (close * 0.95);
    const resistance = r.resistance_1 ?? (close * 1.05);
    const defense = r.swing_defense ?? support;

    const totalRange = resistance - support;
    const pct = totalRange > 0 ? Math.max(0, Math.min(100, ((close - support) / totalRange) * 100)) : 50;
    const defensePct = totalRange > 0 ? Math.max(0, Math.min(100, ((defense - support) / totalRange) * 100)) : 20;

    const isBroken = close <= defense;
    const barClass = isBroken ? "pr-bar-fill danger" : "pr-bar-fill safe";
    const indicatorClass = isBroken ? "pr-bar-indicator danger" : "pr-bar-indicator";
    const indicatorTextClass = isBroken ? "pr-bar-indicator-text danger" : "pr-bar-indicator-text";

    return (
      <div className="price-range-bar" style={{ position: "relative", marginBottom: "16px" }}>
        <div className="pr-bar-track-wrapper">
          <div className={barClass} style={{ left: 0, width: `${pct}%` }} />
          <div 
            className="pr-bar-defense-mark" 
            style={{ left: `${defensePct}%` }} 
            data-defense={`防守 ${defense}`}
          />
          <div className={indicatorClass} style={{ left: `${pct}%` }}>
            <span className={indicatorTextClass}>收盤 ${close}</span>
          </div>
        </div>
        <div className="pr-bar-labels" style={{ marginTop: "18px" }}>
          <span>支撐 {support}</span>
          <span>壓力 {resistance}</span>
        </div>
      </div>
    );
  };

  return (
    <div className="panel fade-in" style={{ padding: "24px" }}>
      <h2 style={{ fontSize: "22px", margin: "0 0 6px", fontWeight: "800", color: "var(--text)" }}>黃金逃頂與交易決策雷達</h2>
      <p style={{ color: "var(--muted)", fontSize: "14px", lineHeight: "1.6", margin: "0 0 20px", maxWidth: "68ch" }}>
        運用真實波動幅度 (ATR) 追蹤與樞軸點 (Pivot) 預測，提供明日的關鍵價位。跌破防守價建議波段停利，突破壓力價則面臨短線賣壓。
      </p>

      {/* 持股篩選 Toggle 開關 */}
      <div style={{ 
        display: "flex", 
        alignItems: "center", 
        gap: "10px", 
        marginBottom: "24px",
        background: "var(--panel-2)",
        padding: "10px 16px",
        borderRadius: "10px",
        width: "fit-content",
        border: "1px solid var(--line)"
      }}>
        <span style={{ fontSize: "13px", fontWeight: "700", color: "var(--text)" }}>
          僅顯示我的持股標的 ({portfolio?.length || 0} 檔)
        </span>
        <button 
          type="button"
          onClick={() => setFilterByPortfolio(!filterByPortfolio)}
          style={{
            position: "relative",
            width: "48px",
            height: "24px",
            borderRadius: "12px",
            background: filterByPortfolio ? "var(--accent)" : "rgba(195,178,160,0.3)",
            border: "none",
            cursor: "pointer",
            transition: "background 0.3s ease"
          }}
        >
          <div style={{
            position: "absolute",
            top: "2px",
            left: filterByPortfolio ? "26px" : "2px",
            width: "20px",
            height: "20px",
            borderRadius: "50%",
            background: filterByPortfolio ? "#000" : "#fff",
            transition: "left 0.3s cubic-bezier(0.16, 1, 0.3, 1), background-color 0.3s ease",
            boxShadow: "0 1px 3px rgba(0,0,0,0.2)"
          }} />
        </button>
      </div>

      {records.length === 0 ? (
        <div className="panel" style={{ padding: "40px 20px", textAlign: "center", color: "var(--muted)", borderRadius: "12px", border: "1px dashed var(--line)" }}>
          目前持股清單中尚無黃金逃頂監控標的。<br/>
          您可以前往「我的持股」新增標的，或者關閉上方「僅顯示我的持股標的」開關以查看全市場選股。
        </div>
      ) : (
        <>
          {/* 頂部焦點雷達卡片 */}
          <div className="golden-radar-grid">
            {[...records]
              .sort((a: any, b: any) => (b.win_rate ?? 0) - (a.win_rate ?? 0))
              .slice(0, 3)
              .map((r: any) => {
                const decision = getDecision(r);
                return (
                  <div key={`radar-${r.stock_id}`} className="golden-radar-card" onClick={() => onNavigateToStock(r.stock_id)} style={{ cursor: "pointer" }}>
                    <div className="gr-card-header">
                      <div className="gr-stock-title">
                        <strong>{r.stock_name}</strong>
                        <span>{r.stock_id}</span>
                      </div>
                      <div className="gr-win-badge">勝率 {r.win_rate}%</div>
                    </div>
                    
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "rgba(217, 119, 6, 0.04)", padding: "8px 12px", borderRadius: "8px", border: "1px solid rgba(217,119,6,0.1)", margin: "4px 0" }}>
                      <span style={{ fontSize: "11px", color: "var(--muted)", fontWeight: "600" }}>操作建議</span>
                      <span className={decision.badgeClass} style={{ fontSize: "11px" }}>{decision.action}</span>
                    </div>

                    <div className="gr-price-display">
                      <span>今日收盤價</span>
                      <strong>${r.close}</strong>
                    </div>
                    {renderPriceRangeBar(r)}
                  </div>
                );
              })}
          </div>

          <div className="table-wrapper" style={{ marginTop: "16px", border: "1px solid var(--line)", borderRadius: "14px", overflow: "hidden" }}>
            <table className="data-table" style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "var(--panel-2)" }}>
                  <th style={{ textAlign: "left", padding: "14px 16px", color: "var(--muted)", fontWeight: "800", fontSize: "13px", letterSpacing: "0.05em" }}>代號/名稱</th>
                  <th className="num" style={{ textAlign: "right", padding: "14px 16px", color: "var(--muted)", fontWeight: "800", fontSize: "13px", letterSpacing: "0.05em" }}>最新收盤</th>
                  <th className="num" style={{ textAlign: "right", padding: "14px 16px", color: "var(--muted)", fontWeight: "800", fontSize: "13px", letterSpacing: "0.05em" }}>波段防守(停利)</th>
                  <th className="num" style={{ textAlign: "right", padding: "14px 16px", color: "var(--muted)", fontWeight: "800", fontSize: "13px", letterSpacing: "0.05em" }}>明日壓力(短空)</th>
                  <th className="num" style={{ textAlign: "right", padding: "14px 16px", color: "var(--muted)", fontWeight: "800", fontSize: "13px", letterSpacing: "0.05em" }}>明日支撐(短多)</th>
                  <th style={{ textAlign: "left", padding: "14px 16px", color: "var(--muted)", fontWeight: "800", fontSize: "13px", letterSpacing: "0.05em" }}>量化交易決策與時間建議</th>
                  <th className="num" style={{ textAlign: "right", padding: "14px 16px", color: "var(--muted)", fontWeight: "800", fontSize: "13px", letterSpacing: "0.05em" }}>預期勝率</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r: any) => {
                  const isBroken = r.close <= r.swing_defense;
                  const decision = getDecision(r);
                  return (
                    <tr key={r.stock_id} onClick={() => onNavigateToStock(r.stock_id)} className="clickable" style={{ borderTop: "1px solid var(--line)", transition: "background 0.2s" }}>
                      <td style={{ padding: "12px 16px" }}>
                        <div style={{ display: "flex", alignItems: "center" }}>
                          {isBroken && <span className="exit-warning-badge" style={{ display: "inline-flex", justifyContent: "center", alignItems: "center" }}>[逃頂]</span>}
                          <div style={{ fontWeight: 800, color: "var(--text)" }}>{r.stock_name}</div>
                        </div>
                        <div style={{ fontSize: "11px", color: "var(--muted)", fontFamily: "Outfit, monospace", marginTop: "2px" }}>{r.stock_id}</div>
                      </td>
                      <td className="num" style={{ textAlign: "right", padding: "12px 16px", fontWeight: "800", fontFamily: "Outfit, monospace", fontVariantNumeric: "tabular-nums", color: "var(--text)" }}>{r.close}</td>
                      <td className="num" style={{ textAlign: "right", padding: "12px 16px", fontFamily: "Outfit, monospace", fontVariantNumeric: "tabular-nums" }}>
                        {isBroken ? (
                          <span className="defense-broken-badge">{r.swing_defense ?? "-"}</span>
                        ) : (
                          <span style={{ color: "var(--text)", fontWeight: "600" }}>{r.swing_defense ?? "-"}</span>
                        )}
                      </td>
                      <td className="num" style={{ textAlign: "right", padding: "12px 16px", fontWeight: "600", fontFamily: "Outfit, monospace", fontVariantNumeric: "tabular-nums", color: "var(--muted)" }}>
                        {r.resistance_1 ?? "-"}
                      </td>
                      <td className="num" style={{ textAlign: "right", padding: "12px 16px", fontFamily: "Outfit, monospace", fontVariantNumeric: "tabular-nums", color: "var(--muted)" }}>{r.support_1 ?? "-"}</td>
                      <td style={{ padding: "12px 16px" }}>
                        <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                          <div style={{ display: "flex", alignItems: "center" }}>
                            <span className={decision.badgeClass} style={{ flexShrink: 0 }}>{decision.action}</span>
                            <span style={{ fontSize: "11px", color: "var(--text)", marginLeft: "6px", fontWeight: "700", fontFamily: "Outfit, monospace" }}>{decision.price}</span>
                          </div>
                          <div style={{ fontSize: "11px", color: "var(--muted)", marginTop: "2px" }}>{decision.timing}</div>
                        </div>
                      </td>
                      <td className="num" style={{ textAlign: "right", padding: "12px 16px", color: "var(--accent)", fontWeight: "800", fontFamily: "Outfit, monospace" }}>{r.win_rate}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function PortfolioPage({ datasets, portfolio, setPortfolio, onNavigateToStock }: { datasets: Record<string, DatasetBox>; portfolio: PortfolioItem[]; setPortfolio: (p: PortfolioItem[]) => void; onNavigateToStock: (id: string) => void }) {
  const [newStock, setNewStock] = useState("");
  const [newShares, setNewShares] = useState("");
  const [newPrice, setNewPrice] = useState("");
  const [formError, setFormError] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editShares, setEditShares] = useState("");
  const [editPrice, setEditPrice] = useState("");

  const syncPortfolio = (next: PortfolioItem[]) => {
    setPortfolio(next);
    localStorage.setItem("tw_stock_portfolio", JSON.stringify(next));
    fetch("http://localhost:3000/api/portfolio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(next)
    }).catch(e => console.error("Failed to sync portfolio", e));
  };

  const handleAdd = () => {
    const id = newStock.trim().toUpperCase();
    const shares = Number(newShares);
    const buyPrice = Number(newPrice);

    if (!id || !Number.isFinite(shares) || !Number.isFinite(buyPrice) || shares <= 0 || buyPrice <= 0) {
      setFormError("請完整填寫代號、股數與買進成本價，且數值需大於 0。");
      return;
    }

    const existingIdx = portfolio.findIndex(p => p.id === id);
    let next = [...portfolio];

    if (existingIdx >= 0) {
      next[existingIdx] = { id, shares, buyPrice };
    } else {
      next.push({ id, shares, buyPrice });
    }

    syncPortfolio(next);
    setNewStock("");
    setNewShares("");
    setNewPrice("");
    setFormError("");
  };

  const handleRemove = (id: string) => {
    const next = portfolio.filter(p => p.id !== id);
    syncPortfolio(next);
  };

  const startEdit = (item: PortfolioItem) => {
    setEditingId(item.id);
    setEditShares(String(item.shares));
    setEditPrice(String(item.buyPrice));
    setFormError("");
  };

  const saveEdit = (id: string) => {
    const shares = Number(editShares);
    const buyPrice = Number(editPrice);
    if (!Number.isFinite(shares) || !Number.isFinite(buyPrice) || shares <= 0 || buyPrice <= 0) {
      setFormError("編輯持股時，股數與成本價都必須大於 0。");
      return;
    }
    const next = portfolio.map(item => item.id === id ? { ...item, shares, buyPrice } : item);
    syncPortfolio(next);
    setEditingId(null);
    setEditShares("");
    setEditPrice("");
    setFormError("");
  };

  const alphaPayload = datasets.stockAlpha?.data;
  const goldenPayload = datasets.goldenExit?.data;

  const alphaRecords = Array.isArray(alphaPayload?.records) ? alphaPayload.records : [];
  const goldenRecords = Array.isArray(goldenPayload?.records) ? goldenPayload.records : [];

  const getFlowStatus = (alpha: any, sector: any, pl: number): FlowStatus => {
    const flow = Number(alpha?.net_5d_yi ?? alpha?.net_20d_yi ?? sector?.net_5d_yi ?? sector?.net_20d_yi);
    if (Number.isFinite(flow)) return flow > 0 ? "inflow" : flow < 0 ? "outflow" : "neutral";
    return pl > 0 ? "inflow" : pl < 0 ? "outflow" : "neutral";
  };

  const getRecommendationStatus = (adviceClass: string, plPct: number, score: number | undefined): RecommendationStatus => {
    if (plPct >= 35) return "過熱";
    if (adviceClass === "sell") return "避開";
    if (Number.isFinite(score) && Number(score) >= 80) return "分批觀察";
    if (plPct < 0) return "等待確認";
    return "觀察";
  };

  const getRiskScore = (alpha: any, plPct: number): number => {
    const vol = Number(alpha?.Vol_20d ?? alpha?.sentiment_temperature);
    const lossRisk = plPct < 0 ? Math.min(45, Math.abs(plPct) * 2) : 0;
    const overheatRisk = plPct > 30 ? Math.min(45, (plPct - 30) * 1.2) : 0;
    const volatilityRisk = Number.isFinite(vol) ? Math.min(40, Math.abs(vol)) : 12;
    return Math.min(100, volatilityRisk + lossRisk + overheatRisk);
  };

  const buildTrend20d = (currentPrice: number, plPct: number, changePct: number | undefined): number[] => {
    const end = Number.isFinite(currentPrice) && currentPrice > 0 ? currentPrice : 100;
    const drift = Math.max(-38, Math.min(38, plPct));
    const start = end / (1 + drift / 100 || 1);
    const dayMove = Number.isFinite(changePct) ? Number(changePct) : 0;
    return Array.from({ length: 20 }, (_, index) => {
      const t = index / 19;
      const wave = Math.sin(index * 0.78) * Math.max(0.25, Math.abs(dayMove) / 3);
      return start + (end - start) * t + wave;
    });
  };

  const firstFiniteNumber = (values: unknown[], fallback?: number): number | undefined => {
    for (const value of values) {
      const numeric = Number(value);
      if (Number.isFinite(numeric)) return numeric;
    }
    return fallback;
  };

  const getStockStats = (item: PortfolioItem) => {
    const alpha = alphaRecords.find((r: any) => String(r.stock_id) === String(item.id) || String(r.stock_code) === String(item.id));
    const golden = goldenRecords.find((r: any) => String(r.stock_id) === String(item.id));
    
    const sectorData = datasets.sectorConstituents?.data;
    const sectorRecords = Array.isArray(sectorData?.records) ? sectorData.records : [];
    const sector = sectorRecords.find((r: any) => String(r.stock_code) === String(item.id));
    const basic = findStockBasic(datasets, item.id);

    const currentPrice = firstFiniteNumber([alpha?.close, golden?.close, sector?.close, basic?.close], item.buyPrice) ?? item.buyPrice;
    const scoreRaw = alpha?.alpha_score ?? alpha?.stock_alpha_v4 ?? alpha?.stock_alpha_v5 ?? alpha?.Alpha_Score_v6 ?? alpha?.Alpha_Score_v5;
    const alphaScore = Number(scoreRaw);
    const score = Number.isFinite(alphaScore) ? alphaScore : "-";

    let advice = { text: "持有", class: "hold" };
    if (golden) {
      if (currentPrice <= golden.swing_defense) advice = { text: "跌破防守 (賣出)", class: "sell" };
      else if (currentPrice >= golden.resistance_1) advice = { text: "達壓力區 (減碼)", class: "sell" };
      else if (Number(score) >= 80) advice = { text: "強勢持有", class: "buy" };
    } else if (Number(score) >= 80) {
      advice = { text: "偏多買進", class: "buy" };
    } else if (Number(score) < 40 && score !== "-") {
      advice = { text: "偏空賣出", class: "sell" };
    }

    const totalCost = item.buyPrice * item.shares;
    const currentValue = currentPrice * item.shares;
    const pl = currentValue - totalCost;
    const plPct = totalCost > 0 ? (pl / totalCost) * 100 : 0;

    const changePct = firstFiniteNumber([alpha?.change_pct, sector?.change_pct, basic?.change_pct]);
    const riskScore = getRiskScore(alpha, plPct);
    const flowStatus = getFlowStatus(alpha, sector, pl);
    const recommendationStatus = getRecommendationStatus(advice.class, plPct, Number.isFinite(alphaScore) ? alphaScore : undefined);
    const trend20d = buildTrend20d(currentPrice, plPct, changePct);

    return {
      name: alpha?.stock_name || golden?.stock_name || sector?.stock_name || basic?.stock_name || "未知",
      industry: alpha?.industry || sector?.sector_name || basic?.industry || basic?.sector_name || "",
      price: currentPrice,
      change: Number.isFinite(changePct) ? `${Number(changePct) > 0 ? "+" : ""}${Number(changePct).toFixed(2)}%` : "-",
      changePct,
      score,
      alphaScore: Number.isFinite(alphaScore) ? alphaScore : undefined,
      riskScore,
      flowStatus,
      recommendationStatus,
      trend20d,
      advice,
      totalCost,
      currentValue,
      pl,
      plPct,
      alphaBreakdown: {
        majorFlow: firstFiniteNumber([alpha?.net_5d_yi, alpha?.net_20d_yi, sector?.net_5d_yi, sector?.net_20d_yi]),
        foreign: firstFiniteNumber([alpha?.foreign_net_yi, alpha?.foreign_5d, alpha?.net_5d_yi]),
        trust: firstFiniteNumber([alpha?.trust_net_yi, alpha?.trust_5d]),
        tradeValue: firstFiniteNumber([alpha?.trade_value_yi, sector?.trade_value_yi, basic?.trade_value_yi]),
        momentum: firstFiniteNumber([alpha?.chg_5d, alpha?.change_pct, changePct]),
        riskPenalty: riskScore,
        reason: alpha?.reason || `${isEtfCode(item.id) ? "ETF" : "股票"}依據報酬率、Alpha 分數、資金流與波動風險產生卡牌狀態。`
      }
    };
  };

  const portfolioRows = portfolio.map(item => ({ item, stats: getStockStats(item) }));
  const totalCost = portfolioRows.reduce((sum, row) => sum + row.stats.totalCost, 0);
  const totalValue = portfolioRows.reduce((sum, row) => sum + row.stats.currentValue, 0);
  const totalProfit = totalValue - totalCost;
  const totalReturn = totalCost > 0 ? (totalProfit / totalCost) * 100 : 0;
  const bestMonster = portfolioRows.reduce(
    (best, row) => row.stats.pl > best.stats.pl ? row : best,
    portfolioRows[0] || { item: { id: "", shares: 0, buyPrice: 0 }, stats: getStockStats({ id: "", shares: 0, buyPrice: 1 }) }
  );

  return (
    <section className="page-stack portfolio-arena">
      <div className="portfolio-scoreboard">
        <div>
          <span className="portfolio-score-eyebrow">Collection Deck</span>
          <h2>我的持股戰鬥牌組</h2>
          <p>每檔持股是一張可編輯的戰鬥卡牌，價格、報酬與狀態會跟著批次資料更新。</p>
        </div>
        <div className="portfolio-score-grid">
          <div>
            <span>總市值</span>
            <strong>{totalValue.toLocaleString("zh-TW", { maximumFractionDigits: 0 })}</strong>
          </div>
          <div>
            <span>投入成本</span>
            <strong>{totalCost.toLocaleString("zh-TW", { maximumFractionDigits: 0 })}</strong>
          </div>
          <div className={totalProfit >= 0 ? "is-win" : "is-loss"}>
            <span>總報酬</span>
            <strong>{totalProfit >= 0 ? "+" : ""}{totalProfit.toLocaleString("zh-TW", { maximumFractionDigits: 0 })}</strong>
          </div>
          <div className={totalReturn >= 0 ? "is-win" : "is-loss"}>
            <span>報酬率</span>
            <strong>{totalReturn >= 0 ? "+" : ""}{totalReturn.toFixed(2)}%</strong>
          </div>
        </div>
        {bestMonster?.item.id ? (
          <div className="portfolio-boss">
            <span>王牌</span>
            <strong>{bestMonster.item.id} {bestMonster.stats.name}</strong>
            <small>{bestMonster.stats.pl >= 0 ? "高昂" : "受傷"} · {bestMonster.stats.plPct.toFixed(2)}%</small>
          </div>
        ) : null}
      </div>

      <div className="portfolio-form-panel">
        <div className="portfolio-add-input">
          <label>
            <span>代號</span>
            <input
              type="text"
              inputMode="numeric"
              placeholder="例如 2330"
              value={newStock}
              onChange={e => setNewStock(e.target.value)}
            />
          </label>
          <label>
            <span>股數</span>
            <input
              type="number"
              min="1"
              placeholder="例如 1000"
              value={newShares}
              onChange={e => setNewShares(e.target.value)}
            />
          </label>
          <label>
            <span>買進成本價</span>
            <input
              type="number"
              min="0"
              step="0.01"
              placeholder="例如 615"
              value={newPrice}
              onChange={e => setNewPrice(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleAdd()}
            />
          </label>
          <button type="button" onClick={handleAdd}>新增 / 儲存</button>
        </div>
        {formError ? <small className="portfolio-form-error">{formError}</small> : null}
      </div>

      {portfolio.length === 0 ? (
        <div className="missing">
          <strong>尚未新增持股</strong>
          <small>請在上方輸入股票資料以開始追蹤。</small>
        </div>
      ) : (
        <div className="portfolio-deck">
          {portfolioRows.map(({ item, stats }, index) => {
            const isEditing = editingId === item.id;
            const cardData: CreatureCardData = {
              stockCode: item.id,
              stockName: stats.name,
              assetType: isEtfCode(item.id) ? "ETF" : "STOCK",
              industry: stats.industry,
              marketValue: stats.currentValue,
              shares: item.shares,
              cost: item.buyPrice,
              profitLoss: stats.pl,
              returnPct: stats.plPct,
              alphaScore: stats.alphaScore,
              riskScore: stats.riskScore,
              flowStatus: stats.flowStatus,
              recommendationStatus: stats.recommendationStatus,
              trend20d: stats.trend20d,
              price: stats.price,
              changePct: stats.changePct,
              totalCost: stats.totalCost,
              alphaBreakdown: stats.alphaBreakdown
            };
            const editPanel = (
              <div className="portfolio-edit-panel creature-edit-panel">
                <label>
                  <span>股數</span>
                  <input value={editShares} type="number" min="1" onChange={event => setEditShares(event.target.value)} />
                </label>
                <label>
                  <span>成本價</span>
                  <input value={editPrice} type="number" min="0" step="0.01" onChange={event => setEditPrice(event.target.value)} />
                </label>
                <div className="portfolio-edit-actions">
                  <button type="button" onClick={() => saveEdit(item.id)}>儲存</button>
                  <button type="button" onClick={() => setEditingId(null)}>取消</button>
                </div>
              </div>
            );

            return (
              <CreatureCard
                key={item.id}
                data={cardData}
                index={index}
                isEditing={isEditing}
                editPanel={editPanel}
                onTitleClick={() => onNavigateToStock(item.id)}
                onEdit={() => startEdit(item)}
                onRemove={() => handleRemove(item.id)}
              />
            );
          })}
        </div>
      )}
    </section>
  );
}

export default App;
