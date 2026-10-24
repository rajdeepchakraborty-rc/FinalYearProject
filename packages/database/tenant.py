"""
Multi-tenancy context and query utilities.

Tenant identity is NEVER trusted from external input.
It is always resolved from the authenticated JWT or API key.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select
from sqlalchemy.orm import Query


# Thread-safe (async-safe) tenant context via contextvars
_current_tenant: ContextVar[uuid.UUID | None] = ContextVar(
    "current_tenant", default=None
)


@dataclass(frozen=True)
class TenantContext:
    """
    Manages the current tenant context using contextvars.
    Safe for async/concurrent use.
    """

    @staticmethod
    def set(company_id: uuid.UUID) -> None:
        """Set the current tenant. Called by auth middleware."""
        _current_tenant.set(company_id)

    @staticmethod
    def get() -> uuid.UUID:
        """Get the current tenant. Raises if not set."""
        tenant = _current_tenant.get()
        if tenant is None:
            raise RuntimeError(
                "Tenant context not set. Ensure authentication middleware ran."
            )
        return tenant

    @staticmethod
    def get_optional() -> uuid.UUID | None:
        """Get the current tenant or None (for system-level operations)."""
        return _current_tenant.get()

    @staticmethod
    def clear() -> None:
        """Clear the tenant context."""
        _current_tenant.set(None)


def tenant_filter(stmt: Select[Any], model: Any) -> Select[Any]:
    """
    Apply tenant filter to a SQLAlchemy select statement.

    Usage:
        stmt = select(Feedback)
        stmt = tenant_filter(stmt, Feedback)
        # Equivalent to: WHERE company_id = <current_tenant>
    """
    company_id = TenantContext.get()
    return stmt.where(model.company_id == company_id)


def tenant_dict() -> dict[str, uuid.UUID]:
    """
    Return a dict with the current tenant for use in INSERT/UPDATE.

    Usage:
        new_feedback = Feedback(**data, **tenant_dict())
    """
    return {"company_id": TenantContext.get()}
