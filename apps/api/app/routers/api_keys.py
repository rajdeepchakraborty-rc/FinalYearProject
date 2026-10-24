"""
API Keys Router — Lifecycle management for company API keys.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.deps import CurrentUser, require_permission
from apps.api.app.models import APIKey
from packages.auth import generate_api_key, validate_scopes
from packages.database import AsyncSessionDep
from packages.schemas.api import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyListItem,
    APIKeyRevokeRequest,
    PaginatedResponse,
)

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("", response_model=PaginatedResponse)
async def list_api_keys(
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
    page: int = 1,
    page_size: int = 20,
):
    """List all active API keys for the current tenant."""
    require_permission(current_user, "api_keys:manage")

    stmt = (
        select(APIKey)
        .where(
            APIKey.company_id == current_user.company_id,
            APIKey.is_active == True,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    keys = result.scalars().all()

    return PaginatedResponse(
        items=[
            APIKeyListItem(
                id=str(k.id),
                name=k.name,
                key_prefix=k.key_prefix,
                scopes=list(k.scopes or []),
                expires_at=k.expires_at,
                last_used_at=k.last_used_at,
                is_active=k.is_active,
                created_at=k.created_at,
            )
            for k in keys
        ],
        page=page,
        page_size=page_size,
        total=len(keys),
    )


@router.post("", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: APIKeyCreateRequest,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
):
    """
    Create a new API key. The full key is returned ONCE and not stored.
    """
    require_permission(current_user, "api_keys:manage")

    if not validate_scopes(body.scopes):
        raise HTTPException(status_code=400, detail="One or more invalid scopes")

    full_key, key_prefix, key_hash = generate_api_key()

    api_key = APIKey(
        id=uuid.uuid4(),
        company_id=current_user.company_id,
        name=body.name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        scopes=body.scopes,
        expires_at=body.expires_at,
        created_by=current_user.user_id,
    )
    db.add(api_key)
    await db.flush()

    logger.info(
        "API key created",
        key_id=str(api_key.id),
        company_id=str(current_user.company_id),
        scopes=body.scopes,
    )

    return APIKeyCreateResponse(
        id=str(api_key.id),
        name=api_key.name,
        key=full_key,  # Shown only once
        key_prefix=key_prefix,
        scopes=body.scopes,
        expires_at=body.expires_at,
        created_at=api_key.created_at,
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
):
    """Revoke (soft-delete) an API key."""
    require_permission(current_user, "api_keys:manage")

    stmt = select(APIKey).where(
        APIKey.id == key_id,
        APIKey.company_id == current_user.company_id,
        APIKey.is_active == True,
    )
    result = await db.execute(stmt)
    key = result.scalar_one_or_none()

    if key is None:
        raise HTTPException(status_code=404, detail="API key not found")

    key.is_active = False
    key.revoked_at = datetime.now()
    await db.flush()

    logger.info("API key revoked", key_id=str(key_id), company_id=str(current_user.company_id))
