# =============================================================
# SignalStream — Worker Dockerfile
# =============================================================
# Multi-stage build for background Kafka workers

# ── Stage 1: Base ────────────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

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

# Default command can be overridden by docker-compose service definition
CMD ["python", "-m", "workers.normalization.main"]

# ── Stage 3: Production ──────────────────────────────────────
FROM base AS production

# Create non-root system user
RUN groupadd -r signalstream && useradd -r -g signalstream signalstream

COPY --chown=signalstream:signalstream . .

USER signalstream

CMD ["python", "-m", "workers.normalization.main"]
