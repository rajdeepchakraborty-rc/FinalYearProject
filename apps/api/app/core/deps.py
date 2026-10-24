"""
SignalStream — FastAPI Dependency Utilities
============================================
Shared dependencies for authentication, authorization, and request context.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.auth import check_permission, decode_access_token, verify_api_key
from packages.database import AsyncSessionDep

logger = structlog.get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    """Resolved principal from JWT or API key."""

    user_id: uuid.UUID | None
    company_id: uuid.UUID
    role: str
    scopes: list[str]
    auth_method: str  # "jwt" | "api_key"


def require_permission(user: CurrentUser, permission: str) -> None:
    """Raise 403 if the user does not have the required permission."""
    if user.auth_method == "api_key":
        if permission not in user.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key missing required scope: {permission}",
            )
    else:
        if not check_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: {permission} required",
            )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
) -> CurrentUser:
    """
    Resolve a JWT bearer token into a CurrentUser.
    Used by protected endpoints requiring a logged-in user.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    return CurrentUser(
        user_id=uuid.UUID(payload.sub),
        company_id=uuid.UUID(payload.cid),
        role=payload.role,
        scopes=[],
        auth_method="jwt",
    )


async def get_current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
) -> CurrentUser:
    """
    Flexible principal resolver that accepts either a JWT or an API key.
    Used by ingestion endpoints that support programmatic access.
    """
    if credentials is None:
        # Check X-API-Key header
        api_key_header = request.headers.get("X-API-Key")
        if api_key_header:
            return await _resolve_api_key(api_key_header, db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required (Bearer token or X-API-Key header)",
        )

    token = credentials.credentials

    # Try JWT first
    try:
        payload = decode_access_token(token)
        return CurrentUser(
            user_id=uuid.UUID(payload.sub),
            company_id=uuid.UUID(payload.cid),
            role=payload.role,
            scopes=[],
            auth_method="jwt",
        )
    except JWTError:
        pass

    # Fall back to API key (Bearer scheme also supports API keys)
    return await _resolve_api_key(token, db)


async def _resolve_api_key(key: str, db: AsyncSession) -> CurrentUser:
    """Resolve an API key string to a CurrentUser."""
    from apps.api.app.models import APIKey

    # Find by prefix (first 16 chars)
    prefix = key[:16]
    result = await db.execute(
        select(APIKey).where(
            APIKey.key_prefix == prefix,
            APIKey.is_active == True,
        )
    )
    api_key = result.scalar_one_or_none()

    if api_key is None or not verify_api_key(key, api_key.key_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Check expiry
    if api_key.expires_at:
        from datetime import datetime, timezone
        if api_key.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has expired",
            )

    # Update last_used_at (fire and forget via flush)
    from datetime import datetime, timezone
    api_key.last_used_at = datetime.now(timezone.utc)

    return CurrentUser(
        user_id=None,
        company_id=api_key.company_id,
        role="api_key",
        scopes=list(api_key.scopes or []),
        auth_method="api_key",
    )


# FastAPI annotated dependency aliases
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
PrincipalDep = Annotated[CurrentUser, Depends(get_current_principal)]
