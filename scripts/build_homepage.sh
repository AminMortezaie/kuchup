#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${ROOT}/.venv/bin/python3"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

# Snapshot country labels from Redis/Postgres into homepage/data/countries.json
# before the static Next export. New marketing pages appear after this rebuild.
"$PYTHON" "$ROOT/scripts/export_homepage_countries.py"
"$PYTHON" "$ROOT/scripts/export_homepage_country_snapshots.py"

cd "$ROOT/homepage"
if [[ ! -d node_modules ]]; then
  npm install --silent
fi
npm run build:flask --silent
