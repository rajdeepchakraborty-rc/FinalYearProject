"""
SignalStream — Authentication Middleware
=========================================
Extracts and validates JWT tokens or API keys from requests.
Sets tenant context for downstream handlers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.models import APIKey, User
from packages.auth import (
    check_permission,
    check_scope,
    decode_access_token,
    verify_api_key,
)
from packages.database import AsyncSessionDep, TenantContext

security_scheme = HTTPBearer(auto_error=False)


class AuthContext:
    """Resolved authentication context."""

    def __init__(
        self,
        user_id: str | None,
        company_id: str,
        role: str,
        auth_type: str,  # "jwt" or "api_key"
        scopes: list[str] | None = None,
    ):
        self.user_id = user_id
        self.company_id = company_id
        self.role = role
        self.auth_type = auth_type
        self.scopes = scopes or []


async def get_auth_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(security_scheme),
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0] if hasattr(AsyncSessionDep, '__metadata__') else lambda: None),
) -> AuthContext:
    """
    Resolve authentication from either JWT or API key.
    Sets TenantContext for the current request.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    token = credentials.credentials

    # Try API key first (starts with "ak_")
    if token.startswith("ak_"):
        return await _authenticate_api_key(token, db)

    # Otherwise try JWT
    return await _authenticate_jwt(token)


async def _authenticate_jwt(token: str) -> AuthContext:
    """Authenticate via JWT access token."""
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Set tenant context — this is the ONLY source of company_id
    TenantContext.set(uuid.UUID(payload.cid))

    return AuthContext(
        user_id=payload.sub,
        company_id=payload.cid,
        role=payload.role,
        auth_type="jwt",
    )


async def _authenticate_api_key(key: str, db: AsyncSession) -> AuthContext:
    """Authenticate via API key."""
    # Extract prefix for lookup
    key_prefix = key[:16]

    stmt = select(APIKey).where(
        APIKey.key_prefix == key_prefix,
        APIKey.is_active == True,
    )
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Verify the full key against the stored hash
    if not verify_api_key(key, api_key.key_hash):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Check expiration
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="API key expired")

    # Update last_used_at
    api_key.last_used_at = datetime.now(timezone.utc)
    await db.flush()

    # Set tenant context from the API key's company_id — NEVER from the request
    TenantContext.set(api_key.company_id)

    return AuthContext(
        user_id=None,
        company_id=str(api_key.company_id),
        role="api_service",
        auth_type="api_key",
        scopes=list(api_key.scopes) if api_key.scopes else [],
    )


def require_permission(permission: str):
    """Dependency factory: check that the current user has a specific permission."""

    async def _check(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if auth.auth_type == "api_key":
            if not check_scope(auth.scopes, permission):
                raise HTTPException(
                    status_code=403,
                    detail=f"API key missing required scope: {permission}",
                )
        else:
            if not check_permission(auth.role, permission):
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions: {permission} required",
                )
        return auth

    return _check
