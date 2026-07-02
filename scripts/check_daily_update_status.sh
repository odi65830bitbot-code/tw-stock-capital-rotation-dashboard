#!/usr/bin/env zsh
set -euo pipefail

ROOT="/Users/maxyu/Documents/台股資金網站"
PLIST="$HOME/Library/LaunchAgents/com.maxyu.tw-stock-daily-update.plist"
LABEL="com.maxyu.tw-stock-daily-update"

cd "$ROOT"

echo "== Daily update schedule =="
echo "Expected: daily 06:00 and 15:30 Asia/Taipei"
if [ -f "$PLIST" ]; then
  echo "LaunchAgent: installed"
  echo "Plist: $PLIST"
else
  echo "LaunchAgent: missing"
fi

if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  echo "launchd: loaded"
else
  echo "launchd: not loaded"
fi

echo
echo "== Latest quality report =="
/usr/bin/python3 - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

root = Path("/Users/maxyu/Documents/台股資金網站")
quality_path = root / "data_quality_report.json"

if not quality_path.exists():
    print("data_quality_report.json: missing")
    raise SystemExit(0)

quality = json.loads(quality_path.read_text(encoding="utf-8"))
print(f"status: {quality.get('status', 'unknown')}")
print(f"generated_at: {quality.get('generated_at', 'N/A')}")
print(f"expected_trade_date: {quality.get('expected_trade_date', 'N/A')}")

for check in quality.get("checks", []):
    if not isinstance(check, dict):
        continue
    name = check.get("name")
    if name in {"market_date_alignment", "recommendation_engine", "moneydj_supplemental_quality"}:
        print(f"{name}: {check.get('status', 'unknown')} - {check.get('message', '')}")

source_policy = quality.get("source_policy", {})
if source_policy:
    print(f"supplemental_only: {', '.join(source_policy.get('supplemental_only', []))}")

raw_sources = quality.get("raw_sources", {})
finmind = raw_sources.get("supplemental", {}).get("finmind", {})
if finmind:
    print(f"finmind_enabled: {finmind.get('enabled')}")
    print(f"finmind_indicator_rows: {finmind.get('indicator_rows')}")
PY

echo
echo "== Public dashboard data =="
/usr/bin/python3 - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

root = Path("/Users/maxyu/Documents/台股資金網站")
for rel in [
    "public/data/market_latest.json",
    "public/data/sector_latest.json",
    "public/data/stock_alpha_latest.json",
    "public/data/recommendations_latest.json",
]:
    path = root / rel
    if not path.exists():
        print(f"{rel}: missing")
        continue
    payload = json.loads(path.read_text(encoding="utf-8"))
    print(f"{rel}: as_of_date={payload.get('as_of_date', 'N/A')} records={len(payload.get('records', []))}")
PY

echo
echo "== Recent logs =="
ls -t logs/update_*.log 2>/dev/null | head -5 || true
echo "launchd stdout: logs/launchd_daily_update.out.log"
echo "launchd stderr: logs/launchd_daily_update.err.log"
