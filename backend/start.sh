#!/bin/sh

# DATA_DIR defaults to /data (Railway volume) or /app/data locally
DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "$DATA_DIR/media" || true

# Restore Telegram session from base64 env var (set this in Railway dashboard)
# Supports both plain base64 and gzip+base64 (for large sessions that exceed Railway's 32KB limit)
if [ -n "$TELEGRAM_SESSION_B64" ]; then
    echo "[start] Restoring Telegram session from TELEGRAM_SESSION_B64..."
    DECODED=$(echo "$TELEGRAM_SESSION_B64" | base64 -d 2>/dev/null)
    if [ $? -ne 0 ]; then
        echo "[start] WARNING: base64 decode failed — skipping session restore."
    else
        # Check if the decoded data is gzip-compressed (magic bytes 1f 8b)
        MAGIC=$(echo "$TELEGRAM_SESSION_B64" | base64 -d 2>/dev/null | head -c2 | od -An -tx1 | tr -d ' ')
        if [ "$MAGIC" = "1f8b" ]; then
            echo "[start] Detected gzip-compressed session, decompressing..."
            if echo "$TELEGRAM_SESSION_B64" | base64 -d 2>/dev/null | gunzip > "$DATA_DIR/telegram.session" 2>/dev/null; then
                echo "[start] Session restored ($(wc -c < "$DATA_DIR/telegram.session") bytes, was gzip)."
            else
                echo "[start] WARNING: gunzip failed — skipping session restore."
                rm -f "$DATA_DIR/telegram.session"
            fi
        else
            if echo "$TELEGRAM_SESSION_B64" | base64 -d > "$DATA_DIR/telegram.session" 2>/dev/null; then
                echo "[start] Session restored ($(wc -c < "$DATA_DIR/telegram.session") bytes)."
            else
                echo "[start] WARNING: Failed to write session — skipping."
                rm -f "$DATA_DIR/telegram.session"
            fi
        fi
    fi
fi

echo "[start] DATA_DIR=$DATA_DIR"
echo "[start] Starting OSINT Dashboard on port ${PORT:-8000}..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
