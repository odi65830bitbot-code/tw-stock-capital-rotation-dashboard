#!/usr/bin/env zsh
set -euo pipefail

ROOT="/Users/maxyu/Documents/台股資金網站"
PYTHON_BIN="${PYTHON_BIN:-/Library/Frameworks/Python.framework/Versions/3.14/bin/python3}"

cd "$ROOT"
mkdir -p logs

if [ -f "$ROOT/secrets-local/finmind.env" ]; then
  set -a
  source "$ROOT/secrets-local/finmind.env"
  set +a
elif [ -f "$ROOT/.env" ]; then
  set -a
  source "$ROOT/.env"
  set +a
fi

"$PYTHON_BIN" "$ROOT/scripts/update_daily.py"
"$PYTHON_BIN" "$ROOT/scripts/fetch_global_news.py"
"$PYTHON_BIN" "$ROOT/scripts/fetch_sectorrotation_reference.py"
"$PYTHON_BIN" "$ROOT/scripts/fetch_financial_statements.py"
"$PYTHON_BIN" "$ROOT/scripts/fetch_sentiment_and_macro.py"
"$PYTHON_BIN" "$ROOT/scripts/build_formal_json_outputs.py"
