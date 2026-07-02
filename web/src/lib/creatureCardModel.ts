// ============================================================
// 台股怪獸卡牌系統 — 資料模型 & 角色 Mapping
// ============================================================

export type FlowStatus = "inflow" | "outflow" | "neutral";

export type RecommendationStatus = "觀察" | "分批觀察" | "等待確認" | "過熱" | "避開" | string;

export type AlphaBreakdown = {
  majorFlow?: number;
  foreign?: number;
  trust?: number;
  tradeValue?: number;
  momentum?: number;
  riskPenalty?: number;
  reason?: string;
};

/** 卡牌接受的完整資料 schema */
export type CreatureCardData = {
  stockCode: string;
  stockName: string;
  assetType: "ETF" | "STOCK";
  industry?: string;
  marketValue: number;
  shares: number;
  cost: number;
  profitLoss: number;
  returnPct: number;
  alphaScore?: number;
  riskScore?: number;
  flowStatus?: FlowStatus;
  recommendationStatus?: RecommendationStatus;
  trend20d?: number[];
  price?: number;
  changePct?: number;
  totalCost?: number;
  alphaBreakdown?: AlphaBreakdown;
  etfConstituents?: {
    stock_code?: string;
    stock_id?: string;
    stock_name?: string;
    weight_pct?: number;
  }[];
  etfPayoutMonths?: string;
  peRatio?: number;
  pbRatio?: number;
  dividendYield?: number;
  exDividendDate?: string;
};

// ── Creature Archetypes ──

export type CreatureType =
  | "dragon"
  | "leaf"
  | "sparkFox"
  | "coinTurtle"
  | "waveWhale"
  | "fireCub"
  | "crystalRabbit"
  | "shadowRisk"
  | "shiba_fortune"
  | "lucky_cat"
  | "fortune_corgi"
  | "wealthy_orange_cat"
  | "lucky_samoyed"
  | "fortune_husky"
  | "fortune_golden_retriever"
  | "fortune_french_bulldog"
  | "fortune_poodle";

export type ProfitStatus =
  | "big_gain"
  | "gain"
  | "neutral"
  | "loss"
  | "big_loss";

export type AlphaGrade = "SSR" | "S" | "A" | "B" | "C";

export type RiskLevel = "low" | "medium" | "high" | "overheat";

export type CreatureProfile = {
  creatureType: CreatureType;
  archetypeLabel: string;
  profitStatus: ProfitStatus;
  alphaGrade: AlphaGrade;
  riskStatus: RiskLevel;
  flowStatus: FlowStatus;
  statusText: string;
  tone: string;
  moodText: string;
  imagePath: string;
  cardColor: { from: string; to: string };
  borderColor: string;
  borderGlow: string;
  creatureFilter: string;
  fortuneText?: string;
  isFortuneAnimal?: boolean;
};

// ── Industry / Attribute → Creature Mapping ──

function getCreatureType(data: CreatureCardData): CreatureType {
  const code = String(data.stockCode || "").trim().toUpperCase();
  
  // 原本的 9 檔持股對應 9 種可愛吉祥物
  if (code === "00405A") return "shiba_fortune";
  if (code === "00878") return "lucky_cat";
  if (code === "009816") return "fortune_corgi";
  if (code === "00981A") return "wealthy_orange_cat";
  if (code === "00987A") return "lucky_samoyed";
  if (code === "2548") return "fortune_husky";
  if (code === "2891") return "fortune_golden_retriever";
  if (code === "3231") return "fortune_french_bulldog";
  if (code === "1591") return "fortune_poodle";

  // 我們強制將所有持股 (Portfolio) 中的股票都映射到吉祥物
  // 為了支持新增的股票，使用 Hash 演算法平均分配這 9 種吉祥物
  const fortuneAnimals: CreatureType[] = [
    "shiba_fortune",
    "lucky_cat",
    "fortune_corgi",
    "wealthy_orange_cat",
    "lucky_samoyed",
    "fortune_husky",
    "fortune_golden_retriever",
    "fortune_french_bulldog",
    "fortune_poodle"
  ];
  
  let sum = 0;
  for (let i = 0; i < code.length; i++) {
    sum += code.charCodeAt(i);
  }
  return fortuneAnimals[sum % fortuneAnimals.length];
}

// ── Profit Status ──

function deriveProfitStatus(returnPct: number): ProfitStatus {
  if (returnPct >= 10) return "big_gain";
  if (returnPct > 0) return "gain";
  if (returnPct === 0) return "neutral";
  if (returnPct > -10) return "loss";
  return "big_loss";
}

// ── Alpha Grade ──

function deriveAlphaGrade(score?: number): AlphaGrade {
  if (score === undefined || score === null) return "C";
  if (score >= 90) return "SSR";
  if (score >= 75) return "S";
  if (score >= 60) return "A";
  if (score >= 40) return "B";
  return "C";
}

// ── Risk Level ──

function deriveRiskLevel(data: CreatureCardData): RiskLevel {
  if (data.recommendationStatus === "過熱") return "overheat";
  const riskScore = data.riskScore;
  if (riskScore === undefined || riskScore === null) return "low";
  if (riskScore >= 70) return "high";
  if (riskScore >= 35) return "medium";
  return "low";
}

// ── Card Visual Config ──

const PROFIT_COLORS: Record<ProfitStatus, { from: string; to: string }> = {
  big_gain: { from: "rgba(217, 119, 6, 0.16)", to: "rgba(234, 179, 8, 0.06)" },
  gain: { from: "rgba(195, 178, 160, 0.18)", to: "rgba(217, 119, 6, 0.06)" },
  neutral: { from: "rgba(100, 116, 139, 0.15)", to: "rgba(51, 65, 85, 0.08)" },
  loss: { from: "rgba(244, 63, 94, 0.15)", to: "rgba(217, 119, 6, 0.08)" },
  big_loss: { from: "rgba(220, 38, 38, 0.22)", to: "rgba(126, 34, 206, 0.12)" },
};

const GRADE_BORDER: Record<AlphaGrade, { color: string; glow: string }> = {
  SSR: {
    color: "rgba(168, 85, 247, 0.4)",
    glow: "none",
  },
  S: {
    color: "rgba(217, 119, 6, 0.4)",
    glow: "none",
  },
  A: {
    color: "rgba(46, 125, 50, 0.35)",
    glow: "none",
  },
  B: {
    color: "rgba(21, 101, 192, 0.35)",
    glow: "none",
  },
  C: {
    color: "rgba(195, 178, 160, 0.3)",
    glow: "none",
  },
};

const CREATURE_FILTER: Record<ProfitStatus, string> = {
  big_gain: "brightness(1.2) saturate(1.3) drop-shadow(0 4px 16px rgba(234,179,8,0.4))",
  gain: "brightness(1.1) drop-shadow(0 4px 12px rgba(234,179,8,0.25))",
  neutral: "drop-shadow(0 4px 12px rgba(0,0,0,0.4))",
  loss: "brightness(0.9) saturate(0.85) drop-shadow(0 4px 12px rgba(244,63,94,0.2))",
  big_loss: "brightness(0.7) saturate(0.6) hue-rotate(15deg) drop-shadow(0 4px 16px rgba(220,38,38,0.3))",
};

const CREATURE_LABELS: Record<CreatureType, string> = {
  leaf: "葉盾獸",
  dragon: "晶龍獸",
  sparkFox: "電狐獸",
  coinTurtle: "金龜獸",
  waveWhale: "浪鯨獸",
  fireCub: "火仔獸",
  crystalRabbit: "晶兔獸",
  shadowRisk: "暗影獸",
  shiba_fortune: "送財柴犬",
  lucky_cat: "招財貓咪",
  fortune_corgi: "福袋柯基",
  wealthy_orange_cat: "富貴橘貓",
  lucky_samoyed: "吉祥耶耶",
  fortune_husky: "幸運二哈",
  fortune_golden_retriever: "發財阿金",
  fortune_french_bulldog: "富貴法鬥",
  fortune_poodle: "福氣貴賓"
};

const CREATURE_TONES: Record<CreatureType, string> = {
  leaf: "tone-green",
  dragon: "tone-blue",
  sparkFox: "tone-yellow",
  coinTurtle: "tone-gold",
  waveWhale: "tone-cyan",
  fireCub: "tone-red",
  crystalRabbit: "tone-pink",
  shadowRisk: "tone-purple",
  shiba_fortune: "tone-gold",
  lucky_cat: "tone-gold",
  fortune_corgi: "tone-gold",
  wealthy_orange_cat: "tone-gold",
  lucky_samoyed: "tone-gold",
  fortune_husky: "tone-gold",
  fortune_golden_retriever: "tone-gold",
  fortune_french_bulldog: "tone-gold",
  fortune_poodle: "tone-gold"
};

const FORTUNE_TEXTS: Record<CreatureType, string> = {
  shiba_fortune: "柴源廣進，財運亨通！",
  lucky_cat: "招財進寶，福氣滿滿！",
  fortune_corgi: "大吉大利，富貴逼人！",
  wealthy_orange_cat: "橘祥如意，盆滿缽滿！",
  lucky_samoyed: "耶耶報喜，好運連連！",
  fortune_husky: "哈來運轉，福祿雙全！",
  fortune_golden_retriever: "金玉滿堂，富貴榮華！",
  fortune_french_bulldog: "法力無邊，鬥志昂揚！",
  fortune_poodle: "貴人相助，財運長紅！",
  // 傳統怪獸 fallback
  leaf: "防守先鋒，穩健如山！",
  dragon: "晶片霸主，大展神威！",
  sparkFox: "極速動能，引領未來！",
  coinTurtle: "財富永續，細水長流！",
  waveWhale: "順風起航，乘風破浪！",
  fireCub: "人氣爆發，火力全開！",
  crystalRabbit: "靈活出擊，奇兵制勝！",
  shadowRisk: "冷靜避險，伺機而動！"
};

const PROFIT_STATUS_LABEL: Record<ProfitStatus, string> = {
  big_gain: "🔥 吉星高照",
  gain: "✨ 財運亨通",
  neutral: "— 平安喜樂",
  loss: "⚠️ 福氣沉澱",
  big_loss: "🛡️ 伺機守財",
};

function getMoodText(profitStatus: ProfitStatus, riskStatus: RiskLevel): string {
  if (riskStatus === "overheat") return "熱情";
  if (profitStatus === "big_gain") return "大喜";
  if (profitStatus === "gain") return "歡喜";
  if (profitStatus === "neutral") return "得意";
  if (profitStatus === "loss") return "沉穩";
  return "蓄力"; // big_loss
}

const creatureAssetMap: Record<CreatureType, string> = {
  leaf: "/creatures/leaf-shield.webp",
  dragon: "/creatures/crystal-dragon.webp",
  sparkFox: "/creatures/electric-fox.webp",
  coinTurtle: "/creatures/coin-turtle.webp",
  waveWhale: "/creatures/wave-whale.webp",
  fireCub: "/creatures/fire-cub.webp",
  crystalRabbit: "/creatures/crystal-rabbit.webp",
  shadowRisk: "/creatures/shadow-risk.webp",
  shiba_fortune: "/creatures/shiba_fortune.png",
  lucky_cat: "/creatures/lucky_cat.png",
  fortune_corgi: "/creatures/fortune_corgi.png",
  wealthy_orange_cat: "/creatures/wealthy_orange_cat.png",
  lucky_samoyed: "/creatures/lucky_samoyed.png",
  fortune_husky: "/creatures/fortune_husky.png",
  fortune_golden_retriever: "/creatures/fortune_golden_retriever.png",
  fortune_french_bulldog: "/creatures/fortune_french_bulldog.png",
  fortune_poodle: "/creatures/fortune_poodle.png"
};

export function getCreatureImagePath(type: CreatureType): string {
  const isFortune = [
    "shiba_fortune",
    "lucky_cat",
    "fortune_corgi",
    "wealthy_orange_cat",
    "lucky_samoyed",
    "fortune_husky",
    "fortune_golden_retriever",
    "fortune_french_bulldog",
    "fortune_poodle"
  ].includes(type);
  return creatureAssetMap[type] || `/creatures/${type}.${isFortune ? "png" : "webp"}`;
}

// ── Public API ──

export function getCreatureProfile(data: CreatureCardData): CreatureProfile {
  const profitStatus = deriveProfitStatus(data.returnPct);
  const alphaGrade = deriveAlphaGrade(data.alphaScore);
  const riskStatus = deriveRiskLevel(data);
  const flowStatus = data.flowStatus || "neutral";
  const creatureType = getCreatureType(data);

  const border = GRADE_BORDER[alphaGrade];
  const isFortune = [
    "shiba_fortune",
    "lucky_cat",
    "fortune_corgi",
    "wealthy_orange_cat",
    "lucky_samoyed",
    "fortune_husky",
    "fortune_golden_retriever",
    "fortune_french_bulldog",
    "fortune_poodle"
  ].includes(creatureType);

  return {
    creatureType,
    archetypeLabel: CREATURE_LABELS[creatureType],
    profitStatus,
    alphaGrade,
    riskStatus,
    flowStatus,
    statusText: PROFIT_STATUS_LABEL[profitStatus],
    tone: CREATURE_TONES[creatureType],
    moodText: getMoodText(profitStatus, riskStatus),
    imagePath: getCreatureImagePath(creatureType),
    cardColor: PROFIT_COLORS[profitStatus],
    borderColor: border.color,
    borderGlow: border.glow,
    creatureFilter: CREATURE_FILTER[profitStatus],
    fortuneText: FORTUNE_TEXTS[creatureType],
    isFortuneAnimal: isFortune
  };
}
