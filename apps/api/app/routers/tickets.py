"""
Tickets Router — Support ticket lifecycle management.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.deps import CurrentUser, require_permission
from apps.api.app.models import Ticket, TicketResolution, TicketRoute
from packages.database import AsyncSessionDep
from packages.events import EventProducer, TOPIC_TICKET_CREATED
from packages.schemas.api import (
    PaginatedResponse,
    TicketCreateRequest,
    TicketListItem,
    TicketResponse,
)
from packages.schemas.events import EventType

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("", response_model=PaginatedResponse)
async def list_tickets(
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
    page: int = 1,
    page_size: int = 20,
    ticket_status: str | None = None,
    priority: str | None = None,
    assigned_team: str | None = None,
):
    """List tickets for the current tenant (paginated, filterable)."""
    require_permission(current_user, "tickets:read")

    query = select(Ticket).where(Ticket.company_id == current_user.company_id)
    if ticket_status:
        query = query.where(Ticket.status == ticket_status)
    if priority:
        query = query.where(Ticket.priority == priority)
    if assigned_team:
        query = query.where(Ticket.assigned_team == assigned_team)

    query = (
        query.order_by(Ticket.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    tickets = result.scalars().all()

    return PaginatedResponse(
        items=[
            TicketListItem(
                id=str(t.id),
                subject=t.subject,
                status=t.status,
                priority=t.priority,
                category=t.category,
                assigned_team=t.assigned_team,
                resolution_type=t.resolution_type,
                created_at=t.created_at,
            )
            for t in tickets
        ],
        page=page,
        page_size=page_size,
        total=len(tickets),
    )


@router.post("", response_model=TicketListItem, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    request: Request,
    body: TicketCreateRequest,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
):
    """Create a support ticket and dispatch it for AI routing."""
    require_permission(current_user, "tickets:manage")

    ticket = Ticket(
        id=uuid.uuid4(),
        company_id=current_user.company_id,
        subject=body.subject,
        description=body.description,
        priority=body.priority,
        category=body.category,
        status="open",
        metadata=body.metadata or {},
    )
    db.add(ticket)
    await db.flush()

    # Publish ticket for AI routing
    producer: EventProducer = request.app.state.producer
    await producer.send_envelope(
        topic=TOPIC_TICKET_CREATED,
        event_type=EventType.TICKET_CREATED,
        company_id=str(current_user.company_id),
        payload={
            "ticket_id": str(ticket.id),
            "subject": ticket.subject,
            "description": ticket.description,
            "priority": ticket.priority,
            "category": ticket.category,
        },
        producer_name="api",
    )

    logger.info(
        "Ticket created",
        ticket_id=str(ticket.id),
        company_id=str(current_user.company_id),
    )

    return TicketListItem(
        id=str(ticket.id),
        subject=ticket.subject,
        status=ticket.status,
        priority=ticket.priority,
        category=ticket.category,
        assigned_team=ticket.assigned_team,
        resolution_type=ticket.resolution_type,
        created_at=ticket.created_at,
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
):
    """Get a ticket with its routing and resolution history."""
    require_permission(current_user, "tickets:read")

    stmt = select(Ticket).where(
        Ticket.id == ticket_id,
        Ticket.company_id == current_user.company_id,
    )
    result = await db.execute(stmt)
    ticket = result.scalar_one_or_none()

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return TicketResponse(
        id=str(ticket.id),
        subject=ticket.subject,
        description=ticket.description,
        status=ticket.status,
        priority=ticket.priority,
        category=ticket.category,
        assigned_team=ticket.assigned_team,
        resolution_type=ticket.resolution_type,
        resolved_at=ticket.resolved_at,
        sla_deadline=ticket.sla_deadline,
        metadata=ticket.metadata,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


@router.patch("/{ticket_id}/resolve", response_model=TicketListItem)
async def resolve_ticket(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
):
    """Manually mark a ticket as resolved by a human agent."""
    require_permission(current_user, "tickets:manage")

    stmt = select(Ticket).where(
        Ticket.id == ticket_id,
        Ticket.company_id == current_user.company_id,
    )
    result = await db.execute(stmt)
    ticket = result.scalar_one_or_none()

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.status == "resolved":
        raise HTTPException(status_code=400, detail="Ticket already resolved")

    from datetime import datetime, timezone
    ticket.status = "resolved"
    ticket.resolution_type = "human"
    ticket.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    return TicketListItem(
        id=str(ticket.id),
        subject=ticket.subject,
        status=ticket.status,
        priority=ticket.priority,
        category=ticket.category,
        assigned_team=ticket.assigned_team,
        resolution_type=ticket.resolution_type,
        created_at=ticket.created_at,
    )
