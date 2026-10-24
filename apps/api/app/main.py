"""
SignalStream — Main FastAPI Application
========================================
Entry point for the API server. Assembles middleware, routers, and lifecycle hooks.
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, make_asgi_app

from apps.api.app.core.config import get_settings
from apps.api.app.core.redis import close_redis
from apps.api.app.routers import (
    analytics,
    api_keys,
    auth,
    feedback,
    health,
    integrations,
    tickets,
    users,
)
from packages.database.engine import close_engine
from packages.events import EventProducer
from packages.logging import setup_logging, bind_context, clear_context

# ─── Metrics ─────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
)

# ─── Lifecycle ───────────────────────────────────────────────

_producer: EventProducer | None = None


def get_producer() -> EventProducer:
    if _producer is None:
        raise RuntimeError("Kafka producer not initialized")
    return _producer


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    global _producer

    setup_logging()
    logger = structlog.get_logger("api")
    logger.info("Starting SignalStream API")

    # Start Kafka producer
    _producer = EventProducer()
    await _producer.start()
    app.state.producer = _producer

    logger.info("SignalStream API started", version=get_settings().APP_VERSION)

    yield

    # Shutdown
    logger.info("Shutting down SignalStream API")
    await _producer.stop()
    await close_redis()
    await close_engine()
    logger.info("SignalStream API stopped")


# ─── Application Factory ────────────────────────────────────


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="SignalStream API",
        description="AI-Powered Dynamic Customer Feedback & Brand Crisis Intelligence Platform",
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.APP_DEBUG else None,
        redoc_url="/redoc" if settings.APP_DEBUG else None,
        lifespan=lifespan,
    )

    # ─── CORS ────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Correlation-ID"],
    )

    # ─── Request Tracking Middleware ─────────────────────────

    @app.middleware("http")
    async def request_tracking(request: Request, call_next) -> Response:
        """Add request ID, track duration, emit metrics."""
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))

        # Bind to structlog context for this request
        bind_context(
            request_id=request_id,
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
        )

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status="500",
            ).inc()
            raise
        finally:
            duration = time.perf_counter() - start_time
            clear_context()

        # Add tracking headers to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Response-Time"] = f"{duration:.4f}"

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

        # Metrics
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=str(response.status_code),
        ).inc()
        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=request.url.path,
        ).observe(duration)

        return response

    # ─── Routers ─────────────────────────────────────────────

    app.include_router(health.router, tags=["Health"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
    app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
    app.include_router(api_keys.router, prefix="/api/v1/api-keys", tags=["API Keys"])
    app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["Feedback"])
    app.include_router(tickets.router, prefix="/api/v1/tickets", tags=["Tickets"])
    app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
    app.include_router(
        integrations.router, prefix="/api/v1/integrations", tags=["Integrations"]
    )

    # ─── Prometheus Metrics ──────────────────────────────────
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    return app


# ─── WSGI Entry Point ───────────────────────────────────────

app = create_app()
