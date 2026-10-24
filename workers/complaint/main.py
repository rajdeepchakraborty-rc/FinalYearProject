"""
SignalStream — Complaint / Issue Worker
========================================
Consumes from feedback.normalized, detects complaints, categories, and severity.
"""

from __future__ import annotations

import asyncio
from typing import Any

from workers.base import BaseWorker


class ComplaintWorker(BaseWorker):
    def __init__(self) -> None:
        super().__init__(
            worker_name="complaint",
            topic="feedback.normalized",
            consumer_group="cg-complaint",
            dlq_topic="dlq.intelligence",
        )

    async def process_message(self, message: dict[str, Any], key: str | None = None) -> None:
        self.log.info("Analyzing complaint and issues", event_id=message.get("event_id"))


def main() -> None:
    worker = ComplaintWorker()
    asyncio.run(worker.start())


if __name__ == "__main__":
    main()
