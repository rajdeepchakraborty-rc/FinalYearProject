"""
SignalStream — Normalization Worker
====================================
Consumes from feedback.raw, performs PII masking and schema normalization,
and produces canonical events to feedback.normalized.
"""

from __future__ import annotations

import asyncio
from typing import Any

from workers.base import BaseWorker


class NormalizationWorker(BaseWorker):
    def __init__(self) -> None:
        super().__init__(
            worker_name="normalization",
            topic="feedback.raw",
            consumer_group="cg-normalization",
            dlq_topic="dlq.feedback.raw",
        )

    async def process_message(self, message: dict[str, Any], key: str | None = None) -> None:
        self.log.info("Processing raw feedback event", event_id=message.get("event_id"))
        # Phase 6 will expand full PII detection and canonical schema parsing


def main() -> None:
    worker = NormalizationWorker()
    asyncio.run(worker.start())


if __name__ == "__main__":
    main()
