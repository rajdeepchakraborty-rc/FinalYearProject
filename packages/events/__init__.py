"""
SignalStream — Kafka Event Bus
===============================
Async Kafka producer and consumer with idempotency, retries, and DLQ support.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

import structlog
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError
from pydantic import BaseModel

from packages.schemas.events import EventEnvelope

logger = structlog.get_logger(__name__)

# ─── Topic Constants ─────────────────────────────────────────

TOPIC_FEEDBACK_RAW = "feedback.raw"
TOPIC_FEEDBACK_NORMALIZED = "feedback.normalized"
TOPIC_FEEDBACK_ENRICHED = "feedback.enriched"
TOPIC_SENTIMENT_EVENTS = "sentiment.events"
TOPIC_ISSUE_EVENTS = "issue.events"
TOPIC_TREND_EVENTS = "trend.events"
TOPIC_CRISIS_EVENTS = "crisis.events"
TOPIC_ROOTCAUSE_EVENTS = "rootcause.events"
TOPIC_DEMAND_EVENTS = "demand.events"
TOPIC_PRODUCT_EVENTS = "product.events"
TOPIC_SUPPORT_EVENTS = "support.events"
TOPIC_CUSTOMER_RISK_EVENTS = "customer-risk.events"
TOPIC_RECOMMENDATION_EVENTS = "recommendation.events"
TOPIC_TICKET_CREATED = "support.ticket.created"
TOPIC_TICKET_ANALYZED = "support.ticket.analyzed"
TOPIC_TICKET_ROUTED = "support.ticket.routed"
TOPIC_TICKET_RESOLVED = "support.ticket.resolved"
TOPIC_ALERTS = "alerts"

# DLQ Topics
TOPIC_DLQ_FEEDBACK_RAW = "dlq.feedback.raw"
TOPIC_DLQ_FEEDBACK_NORMALIZED = "dlq.feedback.normalized"
TOPIC_DLQ_INTELLIGENCE = "dlq.intelligence"

# Retry Topics
TOPIC_RETRY_FEEDBACK_NORMALIZED = "retry.feedback.normalized"
TOPIC_RETRY_INTELLIGENCE = "retry.intelligence"


# ─── Producer ────────────────────────────────────────────────


class EventProducer:
    """Async Kafka producer with idempotency and structured event serialization."""

    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        bootstrap_servers = os.environ.get(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self._producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            enable_idempotence=True,
            max_request_size=10485760,  # 10MB
            compression_type="lz4",
            linger_ms=10,
        )
        await self._producer.start()
        logger.info("Kafka producer started", bootstrap_servers=bootstrap_servers)

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            logger.info("Kafka producer stopped")

    async def send_event(
        self,
        topic: str,
        event: BaseModel,
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Send a Pydantic event to a Kafka topic."""
        if not self._producer:
            raise RuntimeError("Producer not started")

        event_data = event.model_dump(mode="json")

        # Build Kafka headers
        kafka_headers: list[tuple[str, bytes]] = []
        if headers:
            for k, v in headers.items():
                kafka_headers.append((k, v.encode("utf-8")))

        try:
            await self._producer.send_and_wait(
                topic=topic,
                value=event_data,
                key=key,
                headers=kafka_headers if kafka_headers else None,
            )
            logger.info(
                "Event sent",
                topic=topic,
                key=key,
                event_type=event_data.get("event_type", "unknown"),
            )
        except KafkaError as e:
            logger.error("Failed to send event", topic=topic, error=str(e))
            raise

    async def send_envelope(
        self,
        topic: str,
        event_type: str,
        company_id: str,
        payload: dict[str, Any],
        producer_name: str = "",
        correlation_id: str = "",
    ) -> str:
        """Send an event wrapped in the standard envelope."""
        envelope = EventEnvelope(
            event_type=event_type,
            company_id=company_id,
            producer=producer_name,
            correlation_id=correlation_id,
            payload=payload,
        )
        await self.send_event(
            topic=topic,
            event=envelope,
            key=company_id,
        )
        return envelope.event_id


# ─── Consumer ────────────────────────────────────────────────


class EventConsumer:
    """
    Async Kafka consumer with retry and DLQ support.
    Commits offsets manually after successful processing.
    """

    def __init__(
        self,
        topic: str,
        group_id: str,
        dlq_topic: str = TOPIC_DLQ_INTELLIGENCE,
        max_retries: int = 3,
    ) -> None:
        self.topic = topic
        self.group_id = group_id
        self.dlq_topic = dlq_topic
        self.max_retries = max_retries
        self._consumer: AIOKafkaConsumer | None = None
        self._producer: EventProducer | None = None
        self._running = False

    async def start(self) -> None:
        bootstrap_servers = os.environ.get(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self._consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=bootstrap_servers,
            group_id=self.group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            max_poll_records=100,
            session_timeout_ms=30000,
            heartbeat_interval_ms=10000,
        )
        self._producer = EventProducer()
        await self._producer.start()
        await self._consumer.start()
        self._running = True
        logger.info(
            "Kafka consumer started",
            topic=self.topic,
            group_id=self.group_id,
        )

    async def stop(self) -> None:
        self._running = False
        if self._consumer:
            await self._consumer.stop()
        if self._producer:
            await self._producer.stop()
        logger.info("Kafka consumer stopped", topic=self.topic)

    async def consume(
        self,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """
        Consume messages and process them with the handler.
        Implements retry with exponential backoff and DLQ.
        """
        if not self._consumer:
            raise RuntimeError("Consumer not started")

        import asyncio

        while self._running:
            try:
                batch = await self._consumer.getmany(
                    timeout_ms=1000, max_records=50
                )
                for tp, messages in batch.items():
                    for message in messages:
                        await self._process_message(message, handler)
                    # Commit after processing the batch for this partition
                    await self._consumer.commit()
            except Exception as e:
                logger.error(
                    "Consumer loop error",
                    topic=self.topic,
                    error=str(e),
                )
                await asyncio.sleep(5)

    async def _process_message(
        self,
        message: Any,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Process a single message with retry logic."""
        import asyncio

        retry_delays = [1, 5, 30]  # seconds

        for attempt in range(self.max_retries + 1):
            try:
                await handler(message.value)
                return
            except Exception as e:
                if attempt < self.max_retries:
                    delay = retry_delays[min(attempt, len(retry_delays) - 1)]
                    logger.warning(
                        "Processing failed, retrying",
                        topic=self.topic,
                        attempt=attempt + 1,
                        max_retries=self.max_retries,
                        delay=delay,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)
                else:
                    # Send to DLQ
                    logger.error(
                        "Max retries exceeded, sending to DLQ",
                        topic=self.topic,
                        dlq_topic=self.dlq_topic,
                        error=str(e),
                    )
                    await self._send_to_dlq(message, str(e))

    async def _send_to_dlq(self, message: Any, error: str) -> None:
        """Send a failed message to the dead-letter queue."""
        if not self._producer:
            return

        dlq_event = {
            "original_topic": self.topic,
            "original_key": message.key.decode("utf-8") if message.key else None,
            "original_value": message.value,
            "error": error,
            "consumer_group": self.group_id,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "original_offset": message.offset,
            "original_partition": message.partition,
        }
        try:
            if self._producer._producer:
                await self._producer._producer.send_and_wait(
                    topic=self.dlq_topic,
                    value=json.dumps(dlq_event, default=str).encode("utf-8"),
                )
        except Exception as e:
            logger.error("Failed to send to DLQ", error=str(e))
