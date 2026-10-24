"""
Integrations Router — Manage external integrations (Zendesk, Intercom, CRM, webhooks).
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.deps import CurrentUser, require_permission
from apps.api.app.models import Integration, Webhook
from packages.database import AsyncSessionDep
from packages.schemas.api import (
    IntegrationCreateRequest,
    IntegrationResponse,
    PaginatedResponse,
    WebhookCreateRequest,
    WebhookResponse,
)

router = APIRouter()
logger = structlog.get_logger(__name__)


# ─── Integrations ─────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse)
async def list_integrations(
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
):
    """List all configured integrations for the current tenant."""
    require_permission(current_user, "integrations:manage")

    result = await db.execute(
        select(Integration).where(Integration.company_id == current_user.company_id)
    )
    integrations = result.scalars().all()

    return PaginatedResponse(
        items=[
            IntegrationResponse(
                id=str(i.id),
                provider=i.provider,
                name=i.name,
                is_active=i.is_active,
                config=i.config,
                created_at=i.created_at,
            )
            for i in integrations
        ],
        page=1,
        page_size=len(integrations),
        total=len(integrations),
    )


@router.post("", response_model=IntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_integration(
    body: IntegrationCreateRequest,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
):
    """Configure a new external integration."""
    require_permission(current_user, "integrations:manage")

    # Check for duplicate provider
    existing = await db.execute(
        select(Integration).where(
            Integration.company_id == current_user.company_id,
            Integration.provider == body.provider,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Integration for provider '{body.provider}' already exists",
        )

    integration = Integration(
        id=uuid.uuid4(),
        company_id=current_user.company_id,
        provider=body.provider,
        name=body.name,
        config=body.config,
        is_active=True,
    )
    db.add(integration)
    await db.flush()

    logger.info(
        "Integration created",
        provider=body.provider,
        company_id=str(current_user.company_id),
    )

    return IntegrationResponse(
        id=str(integration.id),
        provider=integration.provider,
        name=integration.name,
        is_active=integration.is_active,
        config=integration.config,
        created_at=integration.created_at,
    )


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    integration_id: uuid.UUID,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
):
    """Disable and remove an integration."""
    require_permission(current_user, "integrations:manage")

    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.company_id == current_user.company_id,
        )
    )
    integration = result.scalar_one_or_none()
    if integration is None:
        raise HTTPException(status_code=404, detail="Integration not found")

    integration.is_active = False
    await db.flush()


# ─── Webhooks ─────────────────────────────────────────────────

@router.get("/webhooks", response_model=PaginatedResponse)
async def list_webhooks(
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
):
    """List all configured webhooks for the current tenant."""
    require_permission(current_user, "integrations:manage")

    result = await db.execute(
        select(Webhook).where(Webhook.company_id == current_user.company_id)
    )
    webhooks = result.scalars().all()

    return PaginatedResponse(
        items=[
            WebhookResponse(
                id=str(w.id),
                url=w.url,
                events=w.events,
                is_active=w.is_active,
                created_at=w.created_at,
            )
            for w in webhooks
        ],
        page=1,
        page_size=len(webhooks),
        total=len(webhooks),
    )


@router.post("/webhooks", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: WebhookCreateRequest,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
):
    """Register a new outbound webhook endpoint."""
    require_permission(current_user, "integrations:manage")

    import secrets
    webhook = Webhook(
        id=uuid.uuid4(),
        company_id=current_user.company_id,
        url=str(body.url),
        events=body.events,
        secret=secrets.token_urlsafe(32),
        is_active=True,
    )
    db.add(webhook)
    await db.flush()

    logger.info("Webhook created", webhook_id=str(webhook.id), company_id=str(current_user.company_id))

    return WebhookResponse(
        id=str(webhook.id),
        url=webhook.url,
        events=webhook.events,
        is_active=webhook.is_active,
        created_at=webhook.created_at,
    )


@router.delete("/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
):
    """Delete a webhook."""
    require_permission(current_user, "integrations:manage")

    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.company_id == current_user.company_id,
        )
    )
    webhook = result.scalar_one_or_none()
    if webhook is None:
        raise HTTPException(status_code=404, detail="Webhook not found")

    webhook.is_active = False
    await db.flush()
