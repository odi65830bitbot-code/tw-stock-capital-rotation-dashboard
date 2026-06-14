import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const app = readFileSync(resolve(root, "src/App.tsx"), "utf8");
const styles = readFileSync(resolve(root, "src/styles.css"), "utf8");
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
    name: "portfolio captures code shares cost and shows profit",
    pass:
      ["代號", "股數", "買進成本價", "獲利", "目前市值"].every((label) => app.includes(label)) &&
      app.includes("tw_stock_portfolio")
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
