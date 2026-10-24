"""
SignalStream — Product Worker
=============================
Consumes from feedback.normalized, extracts product-level bug reports,
usability complaints, and UX metrics.
"""

from __future__ import annotations

import asyncio
from typing import Any

from workers.base import BaseWorker


class ProductWorker(BaseWorker):
    def __init__(self) -> None:
        super().__init__(
            worker_name="product",
            topic="feedback.normalized",
            consumer_group="cg-product",
            dlq_topic="dlq.intelligence",
        )

    async def process_message(self, message: dict[str, Any], key: str | None = None) -> None:
        self.log.info("Analyzing product feedback", event_id=message.get("event_id"))


def main() -> None:
    worker = ProductWorker()
    asyncio.run(worker.start())


if __name__ == "__main__":
    main()
