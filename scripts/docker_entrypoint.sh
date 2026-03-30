#!/bin/sh
set -eu

APP_DIR="${APP_DIR:-/app}"
OPENCLAW_HOME="${OPENCLAW_HOME:-$APP_DIR/.openclaw}"
PROFILE="${RACCOONCLAW_DATA_PROFILE:-clean}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-7891}"

mkdir -p "$OPENCLAW_HOME"

python3 "$APP_DIR/scripts/seed_runtime_data.py" \
  --profile "$PROFILE" \
  --repo-dir "$APP_DIR" \
  --openclaw-home "$OPENCLAW_HOME" \
  --force

exec python3 -m uvicorn app.main:app --host "$HOST" --port "$PORT"
