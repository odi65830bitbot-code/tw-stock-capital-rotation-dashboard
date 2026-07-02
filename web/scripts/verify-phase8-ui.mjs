import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const app = readFileSync(resolve(root, "src/App.tsx"), "utf8");
const styles = readFileSync(resolve(root, "src/styles.css"), "utf8");
const creatureStyles = readFileSync(resolve(root, "src/styles/creature-card.css"), "utf8");
const creatureModel = readFileSync(resolve(root, "src/lib/creatureCardModel.ts"), "utf8");
const creatureCard = readFileSync(resolve(root, "src/components/CreatureCard.tsx"), "utf8");
const creatureStage = readFileSync(resolve(root, "src/components/CreatureStage.tsx"), "utf8");
const miniTrend = readFileSync(resolve(root, "src/components/MiniTrend.tsx"), "utf8");
const alphaBack = readFileSync(resolve(root, "src/components/AlphaBreakdownBack.tsx"), "utf8");
const pkg = JSON.parse(readFileSync(resolve(root, "package.json"), "utf8"));

const checks = [
  {
    name: "loads sector_flow_history.json",
    pass: app.includes("/data/sector_flow_history.json")
  },
  {
    name: "sector chart tabs replace treemap with planetary chart",
    pass:
      app.includes('{ key: "planet", label: "資金行星" }') &&
      !app.includes('{ key: "treemap", label: "板塊圖" }')
  },
  {
    name: "uses Recharts AreaChart for stream chart",
    pass: app.includes("AreaChart") && app.includes("ResponsiveContainer")
  },
  {
    name: "implements stream, planet, and sankey components",
    pass: ["StreamChart", "PlanetChart", "SankeyChart"].every((name) => new RegExp(`function\\s+${name}\\b`).test(app))
  },
  {
    name: "planet chart has time range and volume controls",
    pass: ["1 日", "5 日", "20 日", "資金量體"].every((label) => app.includes(label))
  },
  {
    name: "adds phase 8 chart styles and planetary motion",
    pass: [".sector-chart-view", ".sector-stream-chart", ".planet-chart-container", "@keyframes planetOrbit", ".sankey-ribbon"].every((selector) => styles.includes(selector))
  },
  {
    name: "portfolio captures code shares cost and shows editable card profit",
    pass:
      ["代號", "股數", "買進成本價", "總市值", "總報酬", "編輯"].every((label) => app.includes(label)) &&
      app.includes("tw_stock_portfolio") &&
      app.includes("saveEdit") &&
      app.includes("currentValue = currentPrice * item.shares") &&
      app.includes("pl = currentValue - totalCost") &&
      app.includes("(pl / totalCost) * 100") &&
      app.includes("firstFiniteNumber")
  },
  {
    name: "portfolio uses collectible card monster presentation",
    pass:
      ["CreatureCard", "CreatureCardData", "portfolio-scoreboard"].every((token) => app.includes(token)) &&
      [".creature-card-shell", ".creature-stage", ".creature-body", ".creature-leg", "@keyframes creatureBreath"].every((selector) => creatureStyles.includes(selector))
  },
  {
    name: "creature card is modular and data-driven",
    pass:
      ["CreatureCardData", "getCreatureProfile", "dragon", "leaf", "sparkFox", "coinTurtle", "waveWhale", "fireCub", "crystalRabbit", "shadowRisk"].every((token) => creatureModel.includes(token)) &&
      ["profitStatus", "alphaGrade", "riskStatus", "flowStatus", "recommendationStatus"].every((token) => creatureModel.includes(token)) &&
      ["data-profit-loss", "data-return-pct", "data-market-value", "data-archetype"].every((token) => creatureCard.includes(token))
  },
  {
    name: "all eight original creature archetypes have distinct visual rules",
    pass:
      ["dragon", "leaf", "sparkFox", "coinTurtle", "waveWhale", "fireCub", "crystalRabbit", "shadowRisk"].every((name) => creatureStyles.includes(`.creature-${name}`)) &&
      ["creature-shell", "creature-fin", "creature-flame", "creature-crystal", "shadowMist", "tailSpark", "flameFlicker"].every((token) => creatureStyles.includes(token))
  },
  {
    name: "creature card supports flip detail and mini trend",
    pass:
      creatureCard.includes("setFlipped(true)") &&
      creatureCard.includes("AlphaBreakdownBack") &&
      miniTrend.includes("polyline") &&
      alphaBack.includes("Alpha 拆解")
  },
  {
    name: "creature stage renders full body parts instead of a head-only avatar",
    pass:
      ["creature-body", "creature-arm", "creature-leg", "creature-tail", "creature-wing", "creature-ground-shadow"].every((token) => creatureStage.includes(token) || creatureStyles.includes(`.${token}`))
  },
  {
    name: "declares recharts dependency",
    pass: Boolean(pkg.dependencies?.recharts)
  }
];

let failed = 0;
for (const check of checks) {
  if (check.pass) {
    console.log(`PASS ${check.name}`);
  } else {
    failed += 1;
    console.error(`FAIL ${check.name}`);
  }
}

process.exit(failed === 0 ? 0 : 1);
