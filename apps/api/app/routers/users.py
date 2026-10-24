"""
Users Router — CRUD for users within a tenant.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.core.deps import CurrentUser, require_permission
from apps.api.app.models import Role, User
from packages.auth import hash_password
from packages.database import AsyncSessionDep
from packages.schemas.api import (
    PaginatedResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("", response_model=PaginatedResponse)
async def list_users(
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
    page: int = 1,
    page_size: int = 20,
):
    """List all users in the current tenant."""
    require_permission(current_user, "users:manage")

    stmt = (
        select(User)
        .where(User.company_id == current_user.company_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    users = result.scalars().all()

    return PaginatedResponse(
        items=[
            UserResponse(
                id=str(u.id),
                email=u.email,
                full_name=u.full_name,
                role=u.role.name if u.role else "analyst",
                is_active=u.is_active,
                email_verified=u.email_verified,
                last_login_at=u.last_login_at,
                created_at=u.created_at,
            )
            for u in users
        ],
        page=page,
        page_size=page_size,
        total=len(users),
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
):
    """Create a new user in the current tenant."""
    require_permission(current_user, "users:manage")

    # Check email uniqueness within tenant
    existing = await db.execute(
        select(User).where(
            User.company_id == current_user.company_id,
            User.email == body.email,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already exists")

    # Resolve role
    role_stmt = await db.execute(
        select(Role).where(Role.name == body.role)
    )
    role = role_stmt.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=400, detail=f"Role '{body.role}' not found")

    user = User(
        id=uuid.uuid4(),
        company_id=current_user.company_id,
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role_id=role.id,
    )
    db.add(user)
    await db.flush()

    logger.info("User created", user_id=str(user.id), company_id=str(current_user.company_id))

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=role.name,
        is_active=user.is_active,
        email_verified=user.email_verified,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
):
    """Get a specific user by ID (must belong to current tenant)."""
    require_permission(current_user, "users:manage")

    stmt = select(User).where(
        User.id == user_id, User.company_id == current_user.company_id
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.name if user.role else "analyst",
        is_active=user.is_active,
        email_verified=user.email_verified,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdateRequest,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
):
    """Update a user's profile or role."""
    require_permission(current_user, "users:manage")

    stmt = select(User).where(
        User.id == user_id, User.company_id == current_user.company_id
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.role is not None:
        role_result = await db.execute(select(Role).where(Role.name == body.role))
        role = role_result.scalar_one_or_none()
        if role is None:
            raise HTTPException(status_code=400, detail=f"Role '{body.role}' not found")
        user.role_id = role.id

    await db.flush()
    logger.info("User updated", user_id=str(user.id))

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.name if user.role else "analyst",
        is_active=user.is_active,
        email_verified=user.email_verified,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(AsyncSessionDep.__metadata__[0]
                               if hasattr(AsyncSessionDep, "__metadata__") else lambda: None),
    current_user: CurrentUser = Depends(),
):
    """Deactivate a user (soft delete)."""
    require_permission(current_user, "users:manage")

    stmt = select(User).where(
        User.id == user_id, User.company_id == current_user.company_id
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-deactivation
    if user.id == current_user.user_id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    user.is_active = False
    await db.flush()
    logger.info("User deactivated", user_id=str(user.id))
