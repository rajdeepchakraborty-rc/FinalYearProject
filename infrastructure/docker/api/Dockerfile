# =============================================================
# SignalStream — API Server Dockerfile
# =============================================================
# Multi-stage build: development + production targets

# ── Stage 1: Base ────────────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install -e ".[dev]"

# ── Stage 2: Development (hot-reload) ────────────────────────
FROM base AS development

COPY . .

EXPOSE 8000

CMD ["uvicorn", "apps.api.app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--reload", \
     "--log-level", "info"]

# ── Stage 3: Production ───────────────────────────────────────
FROM base AS production

# Create non-root user
RUN groupadd -r signalstream && useradd -r -g signalstream signalstream

COPY --chown=signalstream:signalstream . .

USER signalstream

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "apps.api.app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--log-level", "info", \
     "--no-access-log"]
