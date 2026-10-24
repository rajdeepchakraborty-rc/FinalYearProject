"""
Analytics Router — Query aggregated intelligence results per tenant.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.deps import CurrentUser, require_permission
from apps.api.app.models import (
    CrisisEvent,
    CustomerRisk,
    Feedback,
    Recommendation,
    SentimentResult,
    TrendSignal,
)
from packages.database import AsyncSessionDep

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("/summary")
async def analytics_summary(
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
    days: int = Query(default=7, ge=1, le=90),
):
    """
    High-level analytics summary for the current tenant over the last N days.
    Used by executive dashboard.
    """
    require_permission(current_user, "analytics:read")
    company_id = current_user.company_id
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Total feedback count
    feedback_count = await db.scalar(
        select(func.count()).where(
            Feedback.company_id == company_id,
            Feedback.created_at >= since,
        )
    )

    # Sentiment breakdown
    sentiment_rows = await db.execute(
        select(SentimentResult.sentiment, func.count().label("cnt"))
        .where(
            SentimentResult.company_id == company_id,
            SentimentResult.created_at >= since,
        )
        .group_by(SentimentResult.sentiment)
    )
    sentiment_breakdown = {row.sentiment: row.cnt for row in sentiment_rows}

    # Active crisis events
    active_crises = await db.scalar(
        select(func.count()).where(
            CrisisEvent.company_id == company_id,
            CrisisEvent.status == "active",
        )
    )

    # High-risk customers
    high_risk_customers = await db.scalar(
        select(func.count()).where(
            CustomerRisk.company_id == company_id,
            CustomerRisk.risk_level.in_(["high", "critical"]),
        )
    )

    # Pending recommendations
    pending_recommendations = await db.scalar(
        select(func.count()).where(
            Recommendation.company_id == company_id,
            Recommendation.status == "pending",
        )
    )

    return {
        "period_days": days,
        "feedback_count": feedback_count or 0,
        "sentiment_breakdown": sentiment_breakdown,
        "active_crisis_events": active_crises or 0,
        "high_risk_customers": high_risk_customers or 0,
        "pending_recommendations": pending_recommendations or 0,
    }


@router.get("/trends")
async def get_trends(
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
    days: int = Query(default=7, ge=1, le=90),
    signal_type: str | None = None,
):
    """Get trend signals for the current tenant."""
    require_permission(current_user, "analytics:read")
    company_id = current_user.company_id
    since = datetime.now(timezone.utc) - timedelta(days=days)

    query = select(TrendSignal).where(
        TrendSignal.company_id == company_id,
        TrendSignal.created_at >= since,
    )
    if signal_type:
        query = query.where(TrendSignal.signal_type == signal_type)

    query = query.order_by(TrendSignal.severity.desc(), TrendSignal.created_at.desc()).limit(50)
    result = await db.execute(query)
    signals = result.scalars().all()

    return {
        "trends": [
            {
                "id": str(s.id),
                "signal_type": s.signal_type,
                "dimension": s.dimension,
                "dimension_value": s.dimension_value,
                "current_value": s.current_value,
                "baseline_value": s.baseline_value,
                "deviation": s.deviation,
                "severity": s.severity,
                "window_start": s.window_start.isoformat() if s.window_start else None,
                "window_end": s.window_end.isoformat() if s.window_end else None,
                "created_at": s.created_at.isoformat(),
            }
            for s in signals
        ]
    }


@router.get("/crisis")
async def get_crisis_events(
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
    active_only: bool = True,
):
    """Get brand crisis events for the current tenant."""
    require_permission(current_user, "analytics:read")

    query = select(CrisisEvent).where(CrisisEvent.company_id == current_user.company_id)
    if active_only:
        query = query.where(CrisisEvent.status == "active")
    query = query.order_by(CrisisEvent.crisis_score.desc())

    result = await db.execute(query)
    events = result.scalars().all()

    return {
        "crisis_events": [
            {
                "id": str(e.id),
                "crisis_score": e.crisis_score,
                "risk_level": e.risk_level,
                "affected_products": e.affected_products,
                "affected_regions": e.affected_regions,
                "reason": e.reason,
                "status": e.status,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ]
    }


@router.get("/recommendations")
async def get_recommendations(
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
    status_filter: str | None = Query(default="pending", alias="status"),
    priority: str | None = None,
):
    """Get business recommendations for the current tenant."""
    require_permission(current_user, "analytics:read")

    query = select(Recommendation).where(
        Recommendation.company_id == current_user.company_id
    )
    if status_filter:
        query = query.where(Recommendation.status == status_filter)
    if priority:
        query = query.where(Recommendation.priority == priority)

    query = query.order_by(Recommendation.priority.asc(), Recommendation.created_at.desc())
    result = await db.execute(query)
    recs = result.scalars().all()

    return {
        "recommendations": [
            {
                "id": str(r.id),
                "category": r.category,
                "recommended_action": r.recommended_action,
                "priority": r.priority,
                "reason": r.reason,
                "expected_impact": r.expected_impact,
                "confidence": r.confidence,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in recs
        ]
    }
