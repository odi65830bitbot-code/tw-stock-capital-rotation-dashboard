// SPDX-License-Identifier: AGPL-3.0-only
// Taiwan adapter for the OpenStock integration. See THIRD_PARTY_NOTICES.md.
export interface ResearchStock {
  code: string;
  name: string;
  market: string;
  industry: string;
  close: number | null;
  changePct: number | null;
  priceDate: string | null;
}

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function normalizeStocks(payload: Record<string, unknown> | null): ResearchStock[] {
  const records = payload?.records;
  if (!Array.isArray(records)) return [];
  const stocks = new Map<string, ResearchStock>();
  for (const value of records) {
    if (!value || typeof value !== "object") continue;
    const row = value as Record<string, unknown>;
    const code = String(row.stock_code ?? row.stock_id ?? "").trim().toUpperCase();
    if (!/^[0-9][0-9A-Z]{3,5}$/.test(code)) continue;
    const name = String(row.stock_name ?? row.name ?? "").trim();
    if (!name || stocks.has(code)) continue;
    stocks.set(code, {
      code, name,
      market: String(row.market ?? "UNKNOWN").toUpperCase(),
      industry: String(row.industry ?? row.sector_name ?? "未分類"),
      close: numberOrNull(row.close),
      changePct: numberOrNull(row.change_pct),
      // Never substitute the batch date for a missing per-symbol price date.
      priceDate: validDate(row.price_date),
    });
  }
  return [...stocks.values()];
}

export function validDate(value: unknown): string | null {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value ? value : null;
}

export function priceAgeDays(date: string | null, now = new Date()): number | null {
  if (!validDate(date)) return null;
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Taipei", year: "numeric", month: "2-digit", day: "2-digit",
  }).format(now);
  return Math.floor((Date.parse(`${today}T00:00:00Z`) - Date.parse(`${date}T00:00:00Z`)) / 86400000);
}

export function tradingViewSymbol(stock: ResearchStock): string | null {
  if (!/^[0-9][0-9A-Z]{3,5}$/.test(stock.code)) return null;
  if (stock.market !== "TWSE" && stock.market !== "TPEX") return null;
  return `${stock.market}:${stock.code}`;
}

export function searchStocks(stocks: ResearchStock[], query: string): ResearchStock[] {
  const term = query.trim().toLocaleLowerCase();
  if (!term) return stocks;
  return stocks.filter(s => `${s.code} ${s.name} ${s.industry}`.toLocaleLowerCase().includes(term))
    .sort((a, b) => Number(b.code.toLowerCase() === term) - Number(a.code.toLowerCase() === term));
}

export function watchCode(label: string): string {
  return label.trim().split(/\s+/)[0].toUpperCase();
}

export function toggleWatchLabel(current: string[], label: string): string[] {
  const code = watchCode(label);
  return current.some(item => watchCode(item) === code)
    ? current.filter(item => watchCode(item) !== code)
    : [...current, label];
}

export function readWatchlist(storage: Pick<Storage, "getItem">): string[] | null {
  try {
    const saved = storage.getItem("tw_stock_watchlist");
    if (saved === null) return null;
    const value: unknown = JSON.parse(saved);
    if (!Array.isArray(value)) return null;
    const seen = new Set<string>();
    return value.filter((item): item is string => {
      if (typeof item !== "string" || !/^[0-9][0-9A-Z]{3,5}$/.test(watchCode(item))) return false;
      const code = watchCode(item);
      if (seen.has(code)) return false;
      seen.add(code);
      return true;
    });
  } catch { return null; }
}

export type WidgetKind = "chart" | "technicals" | "financials" | "profile";
export const WIDGET_SCRIPTS: Record<WidgetKind, string> = {
  chart: "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js",
  technicals: "https://s3.tradingview.com/external-embedding/embed-widget-technical-analysis.js",
  financials: "https://s3.tradingview.com/external-embedding/embed-widget-financials.js",
  profile: "https://s3.tradingview.com/external-embedding/embed-widget-symbol-profile.js",
};

export function widgetConfig(symbol: string, kind: WidgetKind): Record<string, unknown> {
  const shared = { symbol, locale: "zh_TW", width: "100%", height: 520, isTransparent: false };
  if (kind === "chart") return {
    ...shared, theme: "light", autosize: true, interval: "D", timezone: "Asia/Taipei",
    style: "1", allow_symbol_change: false, hide_side_toolbar: false, calendar: false,
  };
  return { ...shared, colorTheme: "light", ...(kind === "technicals" ? { interval: "1D", showIntervalTabs: true } : {}) };
}
