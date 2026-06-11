import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const app = fs.readFileSync(path.join(root, "src", "App.tsx"), "utf8");
const styles = fs.readFileSync(path.join(root, "src", "styles.css"), "utf8");

const checks = [
  {
    name: "loads sector_constituents_latest.json",
    pass: app.includes("/data/sector_constituents_latest.json"),
  },
  {
    name: "renders an interactive SectorTreemap component",
    pass: /function\s+SectorTreemap/.test(app) && /<SectorTreemap\b/.test(app),
  },
  {
    name: "removes the old bubble quadrant component",
    pass: !/BubbleQuadrant/.test(app) && !/bubble-stage/.test(app),
  },
  {
    name: "removes the backtest JSON summary panel",
    pass: !/BacktestSummary/.test(app) && !/<pre>\{JSON\.stringify/.test(app),
  },
  {
    name: "uses a stockLabel helper for code plus stock name",
    pass: /function\s+stockLabel/.test(app) && /stockLabel\(/.test(app),
  },
  {
    name: "adds treemap and truncation styles",
    pass: styles.includes(".sector-treemap") && styles.includes(".stock-label"),
  },
];

const failed = checks.filter((check) => !check.pass);

for (const check of checks) {
  console.log(`${check.pass ? "PASS" : "FAIL"} ${check.name}`);
}

if (failed.length > 0) {
  console.error(`\n${failed.length} Phase 3 UI check(s) failed.`);
  process.exit(1);
}
