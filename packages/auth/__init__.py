"""
SignalStream — Authentication & Authorization Package
======================================================
JWT token management, password hashing, API key utilities, and RBAC.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt
from pydantic import BaseModel

# ─── Configuration ───────────────────────────────────────────

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "CHANGE-ME-IN-PRODUCTION")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.environ.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")
)
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(
    os.environ.get("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")
)

# ─── Password Hashing ───────────────────────────────────────

_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash a password using argon2id."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against an argon2id hash."""
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


# ─── JWT Tokens ──────────────────────────────────────────────


class TokenPayload(BaseModel):
    sub: str  # user_id
    cid: str  # company_id
    role: str
    tid: str  # token_id (for revocation)
    exp: datetime
    iat: datetime


def create_access_token(
    user_id: str,
    company_id: str,
    role: str,
) -> tuple[str, str, datetime]:
    """
    Create a JWT access token.
    Returns: (token_string, token_id, expires_at)
    """
    token_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,
        "cid": company_id,
        "role": role,
        "tid": token_id,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, token_id, expires_at


def create_refresh_token() -> tuple[str, str]:
    """
    Create a refresh token (opaque, not JWT).
    Returns: (raw_token, token_hash)
    """
    raw_token = secrets.token_urlsafe(64)
    token_hash = hash_password(raw_token)
    return raw_token, token_hash


def decode_access_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT access token.
    Raises JWTError on invalid/expired tokens.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return TokenPayload(**payload)
    except JWTError:
        raise


# ─── API Key Management ─────────────────────────────────────

API_KEY_PREFIX = "ak_live_"


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key.
    Returns: (full_key, key_prefix, key_hash)

    - full_key: shown to user ONCE (e.g., ak_live_xxxxxxxxxx...)
    - key_prefix: stored for lookup (first 12 chars)
    - key_hash: argon2id hash stored in database
    """
    random_part = secrets.token_urlsafe(32)
    full_key = f"{API_KEY_PREFIX}{random_part}"
    key_prefix = full_key[:16]  # "ak_live_" + 8 chars
    key_hash = hash_password(full_key)
    return full_key, key_prefix, key_hash


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """Verify a provided API key against the stored hash."""
    return verify_password(provided_key, stored_hash)


# ─── RBAC ────────────────────────────────────────────────────

# System roles and their permissions
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "super_admin": {
        "company:manage", "users:manage", "api_keys:manage",
        "feedback:write", "feedback:read",
        "tickets:manage", "tickets:read",
        "analytics:read", "crisis:manage",
        "integrations:manage", "reports:read", "audit:read",
    },
    "company_admin": {
        "company:manage", "users:manage", "api_keys:manage",
        "feedback:write", "feedback:read",
        "tickets:manage", "tickets:read",
        "analytics:read", "crisis:manage",
        "integrations:manage", "reports:read", "audit:read",
    },
    "manager": {
        "feedback:write", "feedback:read",
        "tickets:manage", "tickets:read",
        "analytics:read", "crisis:manage",
        "reports:read",
    },
    "analyst": {
        "feedback:read", "tickets:read",
        "analytics:read", "reports:read",
    },
    "support_agent": {
        "feedback:read", "tickets:manage", "tickets:read",
    },
}


def check_permission(role: str, permission: str) -> bool:
    """Check if a role has the specified permission."""
    role_perms = ROLE_PERMISSIONS.get(role, set())
    return permission in role_perms


def get_role_permissions(role: str) -> set[str]:
    """Get all permissions for a role."""
    return ROLE_PERMISSIONS.get(role, set())


# ─── API Key Scopes ──────────────────────────────────────────

VALID_SCOPES = {
    "feedback:write",
    "feedback:read",
    "tickets:write",
    "tickets:read",
    "reports:read",
    "webhooks:write",
    "analytics:read",
}


def validate_scopes(scopes: list[str]) -> bool:
    """Validate that all requested scopes are valid."""
    return all(s in VALID_SCOPES for s in scopes)


def check_scope(granted_scopes: list[str], required_scope: str) -> bool:
    """Check if the required scope is in the granted scopes."""
    return required_scope in granted_scopes
