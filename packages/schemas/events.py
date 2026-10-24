"""
SignalStream — Shared Event Schemas
====================================
Canonical event definitions used across all services and workers.
Pydantic v2 models for strict validation and serialization.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ─── Enums ───────────────────────────────────────────────────


class EventType(str, Enum):
    FEEDBACK_CREATED = "customer.feedback.created"
    FEEDBACK_UPDATED = "customer.feedback.updated"
    TICKET_CREATED = "support.ticket.created"
    TICKET_UPDATED = "support.ticket.updated"
    TICKET_RESOLVED = "support.ticket.resolved"
    REVIEW_CREATED = "customer.review.created"
    COMPLAINT_CREATED = "customer.complaint.created"


class Source(str, Enum):
    API = "api"
    WEBHOOK = "webhook"
    CSV = "csv"
    EXCEL = "excel"
    ZENDESK = "zendesk"
    INTERCOM = "intercom"
    CRM = "crm"
    EMAIL = "email"
    SLACK = "slack"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    ROUTED = "routed"
    AUTO_RESOLVED = "auto_resolved"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"


class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class ResolutionType(str, Enum):
    AUTO = "auto"
    DRAFT = "draft"
    HUMAN = "human"
    ESCALATED = "escalated"


# ─── Event Envelope ──────────────────────────────────────────


class EventEnvelope(BaseModel):
    """Standard envelope wrapping every Kafka message."""

    schema_version: str = "1.0"
    event_id: str = Field(default_factory=lambda: f"EVT-{uuid.uuid4().hex[:12]}")
    event_type: str
    company_id: str
    correlation_id: str = Field(
        default_factory=lambda: f"corr-{uuid.uuid4().hex[:12]}"
    )
    trace_id: str = Field(default_factory=lambda: f"trace-{uuid.uuid4().hex[:12]}")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    producer: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


# ─── Raw Feedback (before normalization) ─────────────────────


class RawFeedbackEvent(BaseModel):
    """Raw feedback as received from any source, before normalization."""

    event_id: str = Field(default_factory=lambda: f"EVT-{uuid.uuid4().hex[:12]}")
    company_id: str
    source: Source
    source_event_id: str | None = None
    raw_data: dict[str, Any]
    received_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    idempotency_key: str | None = None
    correlation_id: str = Field(
        default_factory=lambda: f"corr-{uuid.uuid4().hex[:12]}"
    )


# ─── Normalized Feedback ─────────────────────────────────────


class NormalizedFeedbackEvent(BaseModel):
    """Canonical feedback event after normalization."""

    event_id: str
    company_id: str
    source: Source
    source_event_id: str | None = None
    event_type: EventType = EventType.FEEDBACK_CREATED
    timestamp: datetime
    customer_id: str | None = None
    text: str
    text_clean: str | None = None
    product_id: str | None = None
    order_id: str | None = None
    region: str | None = None
    channel: str | None = None
    customer_tier: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    pii_detected: bool = False
    pii_redacted: bool = False
    schema_version: str = "1.0"
    correlation_id: str = ""
    trace_id: str = ""

    @field_validator("text")
    @classmethod
    def text_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Feedback text must not be empty")
        return v.strip()


# ─── Sentiment Result ────────────────────────────────────────


class SentimentEvent(BaseModel):
    """Sentiment analysis result for a feedback event."""

    event_id: str = Field(default_factory=lambda: f"SENT-{uuid.uuid4().hex[:12]}")
    company_id: str
    feedback_id: str
    sentiment: Sentiment
    emotion: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    severity: int = Field(ge=1, le=5, default=3)
    model_id: str = ""
    model_version: str = ""
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    correlation_id: str = ""


# ─── Issue Detection Result ──────────────────────────────────


class IssueEvent(BaseModel):
    """Issue/complaint detection result."""

    event_id: str = Field(default_factory=lambda: f"ISS-{uuid.uuid4().hex[:12]}")
    company_id: str
    feedback_id: str
    issue_type: str
    sub_type: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    severity: int = Field(ge=1, le=5, default=3)
    model_id: str = ""
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    correlation_id: str = ""


# ─── Trend Signal ────────────────────────────────────────────


class TrendSignalEvent(BaseModel):
    """Trend detection signal."""

    event_id: str = Field(default_factory=lambda: f"TRD-{uuid.uuid4().hex[:12]}")
    company_id: str
    signal_type: str  # volume_spike, sentiment_shift, emerging_issue
    dimension: str  # product, region, issue_type
    dimension_value: str
    current_value: float
    baseline_value: float
    deviation: float
    window_start: datetime
    window_end: datetime
    severity: int = Field(ge=1, le=5, default=3)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    correlation_id: str = ""


# ─── Crisis Event ────────────────────────────────────────────


class CrisisEvent(BaseModel):
    """Brand crisis detection result."""

    event_id: str = Field(default_factory=lambda: f"CRI-{uuid.uuid4().hex[:12]}")
    company_id: str
    crisis_score: float = Field(ge=0.0, le=100.0)
    risk_level: RiskLevel
    affected_products: list[str] = Field(default_factory=list)
    affected_regions: list[str] = Field(default_factory=list)
    contributing_signals: list[str] = Field(default_factory=list)
    reason: str = ""
    recommended_actions: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    correlation_id: str = ""


# ─── Root Cause ──────────────────────────────────────────────


class RootCauseEvent(BaseModel):
    """Root cause analysis result."""

    event_id: str = Field(default_factory=lambda: f"RC-{uuid.uuid4().hex[:12]}")
    company_id: str
    issue_type: str
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    contributing_factors: list[dict[str, Any]] = Field(default_factory=list)
    affected_entity_type: str | None = None
    affected_entity_id: str | None = None
    sample_feedback_ids: list[str] = Field(default_factory=list)
    model_id: str = ""
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    correlation_id: str = ""


# ─── Customer Risk ───────────────────────────────────────────


class CustomerRiskEvent(BaseModel):
    """Churn risk assessment result."""

    event_id: str = Field(default_factory=lambda: f"CHR-{uuid.uuid4().hex[:12]}")
    company_id: str
    customer_id: str
    churn_score: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    reasons: list[str] = Field(default_factory=list)
    contributing_feedback_ids: list[str] = Field(default_factory=list)
    model_id: str = ""
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    correlation_id: str = ""


# ─── Recommendation ──────────────────────────────────────────


class RecommendationEvent(BaseModel):
    """Business recommendation."""

    event_id: str = Field(default_factory=lambda: f"REC-{uuid.uuid4().hex[:12]}")
    company_id: str
    category: str
    recommended_action: str
    priority: Priority
    reason: str = ""
    expected_impact: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    source_signals: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    correlation_id: str = ""


# ─── Ticket Routing ──────────────────────────────────────────


class TicketRoutingEvent(BaseModel):
    """JEV routing decision for a ticket."""

    event_id: str = Field(default_factory=lambda: f"RTE-{uuid.uuid4().hex[:12]}")
    company_id: str
    ticket_id: str
    department: str
    queue: str | None = None
    priority: Priority
    sla_minutes: int | None = None
    escalation_level: int = 0
    routing_reason: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    correlation_id: str = ""


# ─── Ticket Resolution ───────────────────────────────────────


class TicketResolutionEvent(BaseModel):
    """Auto-resolution or draft response for a ticket."""

    event_id: str = Field(default_factory=lambda: f"RES-{uuid.uuid4().hex[:12]}")
    company_id: str
    ticket_id: str
    resolution_type: ResolutionType
    response_text: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    policy_matched: str | None = None
    model_id: str = ""
    tools_used: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    correlation_id: str = ""


# ─── Demand Signal ───────────────────────────────────────────


class DemandSignalEvent(BaseModel):
    """Customer demand / feature request signal."""

    event_id: str = Field(default_factory=lambda: f"DEM-{uuid.uuid4().hex[:12]}")
    company_id: str
    signal_type: str  # feature_request, service_gap, pricing_feedback
    description: str
    frequency: int = 1
    sample_feedback_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    correlation_id: str = ""


# ─── Product Insight ─────────────────────────────────────────


class ProductInsightEvent(BaseModel):
    """Product intelligence signal."""

    event_id: str = Field(default_factory=lambda: f"PRD-{uuid.uuid4().hex[:12]}")
    company_id: str
    product_id: str | None = None
    insight_type: str  # defect, strength, weakness, feature_request
    description: str
    sentiment_score: float | None = None
    frequency: int = 1
    sample_feedback_ids: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    correlation_id: str = ""
