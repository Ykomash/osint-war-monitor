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
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend source
COPY backend/ ./

# Built React app — FastAPI will serve it at /
COPY --from=frontend /frontend/dist ./static_frontend

# Pre-create both possible data dirs so StaticFiles never fails on missing dir
RUN mkdir -p /data/media /app/data/media

EXPOSE 8000

CMD ["sh", "start.sh"]
