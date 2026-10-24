"""
Feedback Router — Ingest and query customer feedback signals.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.deps import CurrentUser, get_current_principal
from apps.api.app.models import Customer, Feedback, Product
from packages.database import AsyncSessionDep
from packages.events import EventProducer, TOPIC_FEEDBACK_RAW
from packages.schemas.api import (
    FeedbackIngestRequest,
    FeedbackIngestResponse,
    FeedbackListItem,
    PaginatedResponse,
)
from packages.schemas.events import RawFeedbackEvent, Source

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post(
    "",
    response_model=FeedbackIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_feedback(
    request: Request,
    body: FeedbackIngestRequest,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    principal: CurrentUser = Depends(get_current_principal),
):
    """
    Ingest a customer feedback signal.
    Returns 202 Accepted immediately — processing is async via Kafka.

    Supports both JWT authentication and API key authentication.
    """
    company_id = str(principal.company_id)
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))

    # Idempotency check
    if body.idempotency_key:
        existing = await db.execute(
            select(Feedback).where(
                Feedback.idempotency_key == body.idempotency_key,
                Feedback.company_id == principal.company_id,
            )
        )
        if existing.scalar_one_or_none():
            return FeedbackIngestResponse(
                event_id="duplicate",
                status="duplicate",
                message="Duplicate request — already processed",
            )

    # Resolve customer if external_customer_id provided
    customer_id = None
    if body.customer_external_id:
        cust_result = await db.execute(
            select(Customer).where(
                Customer.company_id == principal.company_id,
                Customer.external_id == body.customer_external_id,
            )
        )
        customer = cust_result.scalar_one_or_none()
        if customer:
            customer_id = str(customer.id)

    # Build raw event
    raw_event = RawFeedbackEvent(
        company_id=company_id,
        source=body.source or Source.API,
        source_event_id=body.source_event_id,
        raw_data=body.model_dump(mode="json"),
        idempotency_key=body.idempotency_key,
        correlation_id=correlation_id,
    )

    # Publish to Kafka
    producer: EventProducer = request.app.state.producer
    await producer.send_event(
        topic=TOPIC_FEEDBACK_RAW,
        event=raw_event,
        key=company_id,
        headers={
            "company_id": company_id,
            "correlation_id": correlation_id,
        },
    )

    logger.info(
        "Feedback ingested",
        event_id=raw_event.event_id,
        company_id=company_id,
        source=str(raw_event.source),
    )

    return FeedbackIngestResponse(
        event_id=raw_event.event_id,
        status="accepted",
        message="Feedback accepted for processing",
    )


@router.get("", response_model=PaginatedResponse)
async def list_feedback(
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
    page: int = 1,
    page_size: int = 20,
    source: str | None = None,
    processing_status: str | None = None,
):
    """List feedback records for the current tenant (paginated)."""
    query = select(Feedback).where(Feedback.company_id == current_user.company_id)

    if source:
        query = query.where(Feedback.source == source)
    if processing_status:
        query = query.where(Feedback.processing_status == processing_status)

    query = query.order_by(Feedback.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        items=[
            FeedbackListItem(
                id=str(f.id),
                event_id=f.event_id,
                source=f.source,
                event_type=f.event_type,
                text=f.text[:200] + "..." if len(f.text) > 200 else f.text,
                processing_status=f.processing_status,
                pii_detected=f.pii_detected,
                created_at=f.created_at,
            )
            for f in items
        ],
        page=page,
        page_size=page_size,
        total=len(items),
    )


@router.get("/{feedback_id}", response_model=FeedbackListItem)
async def get_feedback(
    feedback_id: str,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
):
    """Get a specific feedback record by ID (event_id or UUID)."""
    stmt = select(Feedback).where(
        Feedback.event_id == feedback_id,
        Feedback.company_id == current_user.company_id,
    )
    result = await db.execute(stmt)
    feedback = result.scalar_one_or_none()
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback not found")

    return FeedbackListItem(
        id=str(feedback.id),
        event_id=feedback.event_id,
        source=feedback.source,
        event_type=feedback.event_type,
        text=feedback.text,
        processing_status=feedback.processing_status,
        pii_detected=feedback.pii_detected,
        created_at=feedback.created_at,
    )
