"""
Authentication Router — Login, Refresh, Logout, Password Reset
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.config import get_settings
from apps.api.app.models import Session as SessionModel, User
from packages.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from packages.database import AsyncSessionDep
from packages.schemas.api import (
    LoginRequest,
    LoginResponse,
    PasswordResetRequest,
    RefreshRequest,
    RefreshResponse,
    UserResponse,
)

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0] if hasattr(AsyncSessionDep, '__metadata__') else lambda: None),
):
    """
    Authenticate a user and return JWT access + refresh tokens.
    """
    settings = get_settings()

    # Find user by email
    stmt = select(User).where(User.email == body.email, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Create tokens
    access_token, token_id, expires_at = create_access_token(
        user_id=str(user.id),
        company_id=str(user.company_id),
        role=user.role.name if user.role else "analyst",
    )
    refresh_raw, refresh_hash = create_refresh_token()

    # Store session
    session = SessionModel(
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        user_agent=request.headers.get("User-Agent"),
        ip_address=request.client.host if request.client else None,
        expires_at=datetime.now(timezone.utc) + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        ),
    )
    db.add(session)

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info("User logged in", user_id=str(user.id), company_id=str(user.company_id))

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_raw,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role.name if user.role else "analyst",
            is_active=user.is_active,
            email_verified=user.email_verified,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
        ),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0] if hasattr(AsyncSessionDep, '__metadata__') else lambda: None),
):
    """
    Refresh an access token using a valid refresh token.
    Implements token rotation: old refresh token is invalidated.
    """
    settings = get_settings()

    # Find all active sessions and verify the refresh token
    stmt = select(SessionModel).where(
        SessionModel.revoked_at == None,
        SessionModel.expires_at > datetime.now(timezone.utc),
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    matched_session = None
    for session in sessions:
        if verify_password(body.refresh_token, session.refresh_token_hash):
            matched_session = session
            break

    if matched_session is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Revoke old session (token rotation)
    matched_session.revoked_at = datetime.now(timezone.utc)

    # Get user
    user_stmt = select(User).where(User.id == matched_session.user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Create new tokens
    access_token, token_id, expires_at = create_access_token(
        user_id=str(user.id),
        company_id=str(user.company_id),
        role=user.role.name if user.role else "analyst",
    )
    refresh_raw, refresh_hash = create_refresh_token()

    # Create new session
    new_session = SessionModel(
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        user_agent=matched_session.user_agent,
        ip_address=matched_session.ip_address,
        expires_at=datetime.now(timezone.utc) + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        ),
    )
    db.add(new_session)
    await db.flush()

    return RefreshResponse(
        access_token=access_token,
        refresh_token=refresh_raw,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=204)
async def logout(
    body: RefreshRequest,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0] if hasattr(AsyncSessionDep, '__metadata__') else lambda: None),
):
    """Revoke a refresh token (logout)."""
    stmt = select(SessionModel).where(
        SessionModel.revoked_at == None,
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    for session in sessions:
        if verify_password(body.refresh_token, session.refresh_token_hash):
            session.revoked_at = datetime.now(timezone.utc)
            await db.flush()
            return

    # Silently succeed even if token not found (security best practice)
    return


@router.post("/password-reset", status_code=202)
async def password_reset(body: PasswordResetRequest):
    """
    Request a password reset email.
    Always returns 202 to prevent email enumeration.
    """
    # TODO: Implement email sending
    logger.info("Password reset requested", email=body.email)
    return {"message": "If an account exists with this email, a reset link has been sent."}
