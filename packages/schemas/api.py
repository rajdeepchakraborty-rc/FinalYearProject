"""
SignalStream — API Request/Response Schemas
============================================
Pydantic models for API input validation and response serialization.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


# ─── Auth Schemas ────────────────────────────────────────────


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    email_verified: bool
    last_login_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class PasswordResetRequest(BaseModel):
    email: EmailStr


# ─── User Schemas ────────────────────────────────────────────


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role: str = "analyst"


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


# ─── Company Schemas ─────────────────────────────────────────


class CompanyResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    settings: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanyUpdateRequest(BaseModel):
    name: str | None = None
    settings: dict[str, Any] | None = None


# ─── API Key Schemas ─────────────────────────────────────────


class APIKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    scopes: list[str] = Field(default_factory=lambda: ["feedback:write"])
    expires_in_days: int | None = None
    expires_at: datetime | None = None


class APIKeyListItem(BaseModel):
    """API key metadata displayed in list (no secret)."""
    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class APIKeyCreateResponse(BaseModel):
    """Returned ONCE when creating an API key. The key is never shown again."""
    id: str
    name: str
    key: str  # Full key — shown only once
    key_prefix: str
    scopes: list[str]
    expires_at: datetime | None = None
    created_at: datetime


class APIKeyResponse(BaseModel):
    """API key metadata (without secret)."""
    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    is_active: bool
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class APIKeyRevokeRequest(BaseModel):
    reason: str | None = None


# ─── Feedback Schemas ────────────────────────────────────────


class FeedbackIngestRequest(BaseModel):
    """
    Flexible feedback ingestion schema.
    Companies can submit varying fields — normalization handles mapping.
    """
    text: str | None = None
    message: str | None = None
    feedback: str | None = None
    review_text: str | None = None
    comment: str | None = None

    # Product identifiers (flexible)
    product_id: str | None = None
    product: str | None = None
    sku: str | None = None
    item_id: str | None = None

    # Customer identifiers
    customer_id: str | None = None
    customer_external_id: str | None = None
    customer_email: str | None = None
    user_id: str | None = None

    # Order
    order_id: str | None = None
    order_number: str | None = None

    # Location
    region: str | None = None
    location: str | None = None
    city: str | None = None
    country: str | None = None

    # Channel / Source
    channel: str | None = None
    source: str | None = None
    source_event_id: str | None = None

    # Tier
    customer_tier: str | None = None
    tier: str | None = None

    # Timestamp
    timestamp: datetime | None = None
    created_at: datetime | None = None

    # Idempotency
    idempotency_key: str | None = None

    # Catch-all for extra fields
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("text", "message", "feedback", "review_text", "comment", mode="before")
    @classmethod
    def strip_text(cls, v: str | None) -> str | None:
        if v is not None:
            return v.strip()
        return v

    def get_text(self) -> str:
        """Extract the feedback text from whichever field is populated."""
        for field in [self.text, self.message, self.feedback, self.review_text, self.comment]:
            if field and field.strip():
                return field.strip()
        raise ValueError("At least one text field must be provided")


class FeedbackIngestResponse(BaseModel):
    event_id: str
    status: str = "accepted"
    message: str = "Feedback accepted for processing"


class FeedbackListItem(BaseModel):
    id: str
    event_id: str
    source: str
    event_type: str
    text: str
    processing_status: str
    pii_detected: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class BulkFeedbackResponse(BaseModel):
    status: str = "accepted"
    job_id: str
    total_items: int


class FeedbackDetailResponse(BaseModel):
    id: str
    event_id: str
    source: str
    event_type: str
    text: str
    product_id: str | None = None
    region: str | None = None
    channel: str | None = None
    customer_tier: str | None = None
    processing_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Intelligence Result Schemas ─────────────────────────────


class SentimentResultResponse(BaseModel):
    sentiment: str
    emotion: str | None = None
    confidence: float
    severity: int | None = None

    model_config = {"from_attributes": True}


class IssueResultResponse(BaseModel):
    issue_type: str
    sub_type: str | None = None
    confidence: float
    severity: int | None = None

    model_config = {"from_attributes": True}


class TrendSignalResponse(BaseModel):
    id: str
    signal_type: str
    dimension: str
    dimension_value: str
    current_value: float
    baseline_value: float
    deviation: float
    severity: int
    window_start: datetime
    window_end: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class CrisisResponse(BaseModel):
    id: str
    crisis_score: float
    risk_level: str
    affected_products: list[str]
    affected_regions: list[str]
    reason: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RecommendationResponse(BaseModel):
    id: str
    category: str
    recommended_action: str
    priority: str
    reason: str
    expected_impact: str
    confidence: float
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerRiskResponse(BaseModel):
    id: str
    customer_id: str
    churn_score: float
    risk_level: str
    reasons: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Ticket Schemas ──────────────────────────────────────────


class TicketCreateRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    description: str | None = None
    priority: str = "P3"
    category: str | None = None
    customer_external_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TicketListItem(BaseModel):
    id: str
    subject: str | None = None
    status: str
    priority: str | None = None
    category: str | None = None
    assigned_team: str | None = None
    resolution_type: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketResponse(BaseModel):
    id: str
    external_id: str | None = None
    subject: str | None = None
    description: str | None = None
    status: str
    priority: str | None = None
    category: str | None = None
    assigned_team: str | None = None
    sla_deadline: datetime | None = None
    resolution_type: str | None = None
    resolved_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TicketUpdateRequest(BaseModel):
    status: str | None = None
    priority: str | None = None
    assigned_team: str | None = None
    assigned_agent_id: str | None = None


# ─── Analytics Schemas ───────────────────────────────────────


class OverviewAnalytics(BaseModel):
    total_feedback: int
    total_tickets: int
    open_tickets: int
    avg_sentiment_score: float
    negative_sentiment_pct: float
    active_crises: int
    at_risk_customers: int
    auto_resolved_tickets: int
    top_issues: list[dict[str, Any]]
    sentiment_trend: list[dict[str, Any]]
    period_start: datetime
    period_end: datetime


# ─── Job Status ──────────────────────────────────────────────


class JobStatusResponse(BaseModel):
    id: str
    job_type: str
    status: str
    total_items: int | None = None
    processed_items: int
    failed_items: int
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


# ─── Integration Schemas ────────────────────────────────────


class IntegrationCreateRequest(BaseModel):
    provider: str
    name: str = Field(min_length=1, max_length=255)
    config: dict[str, Any] = Field(default_factory=dict)


class IntegrationResponse(BaseModel):
    id: str
    provider: str
    name: str
    is_active: bool
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookCreateRequest(BaseModel):
    url: str
    events: list[str] = Field(default_factory=list)


class WebhookResponse(BaseModel):
    id: str
    url: str
    events: list[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Pagination ──────────────────────────────────────────────


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


# ─── Health ──────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    uptime_seconds: float = 0.0


class ReadyResponse(BaseModel):
    ready: bool
    checks: dict[str, bool]
