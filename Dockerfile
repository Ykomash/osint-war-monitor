# ── Stage 1: Build React frontend ──────────────────────────────────────────
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci --silent
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python backend ─────────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend source
COPY backend/ ./

# Built React app — FastAPI will serve it at /
COPY --from=frontend /frontend/dist ./static_frontend

# Default data dir (overridden by Railway volume mount via DATA_DIR env var)
RUN mkdir -p /data/media

EXPOSE 8000

CMD ["sh", "start.sh"]
