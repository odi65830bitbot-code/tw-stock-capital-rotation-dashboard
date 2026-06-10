export type Sector = {
  trade_date: string;
  rank: number;
  sector_name: string;
  stock_count: number;
  stocks: string[];
  net_1d_yi: number;
  net_5d_yi: number;
  net_20d_yi: number;
  position: number;
  chg_1d: number;
  chg_5d: number;
  is_bottom_fishing: boolean;
  bottom_score: number;
  source: string;
};

export type SectorStock = {
  trade_date: string;
  sector_rank: number;
  sector_name: string;
  stock_code: string;
  chg_1d: number;
  net_1d_yi: number;
  source: string;
};

export type SectorRotationPayload = {
  generated_at: string;
  source: string;
  source_updated_at: string;
  as_of_date: string;
  market_chg_1d?: number | null;
  is_market_down?: boolean | null;
  sectors: Sector[];
  stock_data: SectorStock[];
};
