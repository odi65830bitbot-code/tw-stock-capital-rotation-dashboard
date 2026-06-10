#!/usr/bin/env zsh
set -euo pipefail

ROOT="/Users/maxyu/Documents/台股資金網站"
SESSION="tw_stock_dashboard"
PORT="8503"
LOG="/tmp/tw_stock_dashboard.log"

cd "$ROOT"

screen -S "$SESSION" -X quit >/dev/null 2>&1 || true

if lsof -ti :"$PORT" >/dev/null 2>&1; then
  lsof -ti :"$PORT" | xargs kill
  sleep 1
fi

screen -dmS "$SESSION" zsh -lc "cd '$ROOT' && python3 -m streamlit run src/dashboard/app.py --server.port $PORT --server.headless true >'$LOG' 2>&1"

sleep 3

if ! lsof -i :"$PORT" -nP >/dev/null 2>&1; then
  echo "Dashboard failed to start. Log:"
  tail -n 80 "$LOG" || true
  exit 1
fi

echo "Dashboard is running: http://127.0.0.1:$PORT"
echo "Log: $LOG"
