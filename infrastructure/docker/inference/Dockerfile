# =============================================================
# SignalStream — Inference Server Dockerfile
# =============================================================
# Multi-stage build for FastAPI ML inference service

# ── Stage 1: Base ────────────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TORCH_HOME=/app/.model_cache/torch \
    HF_HOME=/app/.model_cache/huggingface

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install -e ".[dev]"

# ── Stage 2: Development ─────────────────────────────────────
FROM base AS development

COPY . .

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8100/health || exit 1

CMD ["uvicorn", "services.inference.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8100", \
     "--reload"]

# ── Stage 3: Production ──────────────────────────────────────
FROM base AS production

RUN groupadd -r signalstream && useradd -r -g signalstream signalstream

RUN mkdir -p /app/.model_cache && chown -R signalstream:signalstream /app/.model_cache

COPY --chown=signalstream:signalstream . .

USER signalstream

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8100/health || exit 1

CMD ["uvicorn", "services.inference.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8100", \
     "--workers", "2", \
     "--log-level", "info"]
