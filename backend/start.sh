#!/bin/sh
set -e

# DATA_DIR defaults to /data (Railway volume) or /app/data locally
DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "$DATA_DIR/media"

# Restore Telegram session from base64 env var (set this in Railway dashboard)
if [ -n "$TELEGRAM_SESSION_B64" ]; then
    echo "[start] Restoring Telegram session from TELEGRAM_SESSION_B64..."
    echo "$TELEGRAM_SESSION_B64" | base64 -d > "$DATA_DIR/telegram.session"
    echo "[start] Session restored."
fi

echo "[start] Starting OSINT Dashboard on port ${PORT:-8000}..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
