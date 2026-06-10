import type { Sector, SectorStock } from "./types";

export function fmtYi(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return `${value.toFixed(2)} 億`;
}

export function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function classifySector(sector: Sector): "main" | "rotation" | "watch" | "fade" {
  if (sector.net_5d_yi > 0 && sector.net_1d_yi > 0) return "main";
  if (sector.net_5d_yi > 0 && sector.net_1d_yi <= 0) return "rotation";
  if (sector.net_5d_yi <= 0 && sector.net_1d_yi > 0) return "watch";
  return "fade";
}

export function sectorStocks(stocks: SectorStock[], sectorName: string): SectorStock[] {
  return stocks
    .filter((stock) => stock.sector_name === sectorName)
    .sort((a, b) => b.net_1d_yi - a.net_1d_yi);
}

export function cpCandidates(sectors: Sector[]): Sector[] {
  return [...sectors]
    .filter((sector) => sector.net_5d_yi > 0)
    .sort((a, b) => {
      const aScore = a.net_5d_yi / Math.max(Math.abs(a.chg_5d), 0.8);
      const bScore = b.net_5d_yi / Math.max(Math.abs(b.chg_5d), 0.8);
      return bScore - aScore;
    })
    .slice(0, 6);
}

export function bottomFishing(sectors: Sector[]): Sector[] {
  return [...sectors]
    .filter((sector) => sector.is_bottom_fishing || (sector.net_1d_yi > 0 && sector.chg_1d <= 0))
    .sort((a, b) => b.net_1d_yi - a.net_1d_yi)
    .slice(0, 6);
}
