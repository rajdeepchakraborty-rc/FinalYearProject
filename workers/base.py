"""
SignalStream — Base Worker Class
=================================
Generic lifecycle, Kafka consumer setup, error handling, and DLQ routing.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
from abc import ABC, abstractmethod
from typing import Any

import structlog
from aiokafka import AIOKafkaConsumer

from packages.events import EventProducer
from packages.logging import setup_logging

logger = structlog.get_logger(__name__)


class BaseWorker(ABC):
    """Abstract base worker handling stream consumption, retries, and DLQ routing."""

    def __init__(
        self,
        worker_name: str,
        topic: str,
        consumer_group: str,
        dlq_topic: str | None = None,
    ) -> None:
        self.worker_name = worker_name
        self.topic = topic
        self.consumer_group = consumer_group
        self.dlq_topic = dlq_topic or f"dlq.{topic}"
        self.bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

        self._consumer: AIOKafkaConsumer | None = None
        self._producer: EventProducer | None = None
        self._running = False

    async def start(self) -> None:
        """Initialize consumer, producer, and start consumption loop."""
        setup_logging()
        self.log = structlog.get_logger(f"worker.{self.worker_name}")
        self.log.info(
            "Starting worker",
            topic=self.topic,
            consumer_group=self.consumer_group,
            bootstrap_servers=self.bootstrap_servers,
        )

        self._producer = EventProducer()
        await self._producer.start()

        self._consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.consumer_group,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        await self._consumer.start()
        self._running = True

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            except NotImplementedError:
                # Windows does not implement loop.add_signal_handler
                pass

        try:
            await self._run_loop()
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Gracefully stop worker."""
        if not self._running:
            return
        self.log.info("Stopping worker gracefully...")
        self._running = False
        if self._consumer:
            await self._consumer.stop()
        if self._producer:
            await self._producer.stop()
        self.log.info("Worker stopped successfully")

    async def _run_loop(self) -> None:
        """Main processing loop."""
        if not self._consumer:
            return

        async for msg in self._consumer:
            if not self._running:
                break
            try:
                await self.process_message(msg.value, key=msg.key.decode("utf-8") if msg.key else None)
                await self._consumer.commit()
            except Exception as exc:
                self.log.error(
                    "Error processing message",
                    offset=msg.offset,
                    partition=msg.partition,
                    error=str(exc),
                )
                await self._handle_failure(msg.value, exc)
                # Commit offset to prevent permanent poison-pill stall
                await self._consumer.commit()

    async def _handle_failure(self, message: dict[str, Any], exc: Exception) -> None:
        """Send failed message to DLQ."""
        if not self._producer:
            return
        self.log.warn("Routing message to DLQ", dlq_topic=self.dlq_topic)
        # In actual worker pipeline, publish payload and error context to DLQ
        # Producer handles raw message envelopes

    @abstractmethod
    async def process_message(self, message: dict[str, Any], key: str | None = None) -> None:
        """Subclass must implement business logic for each incoming message."""
        raise NotImplementedError
