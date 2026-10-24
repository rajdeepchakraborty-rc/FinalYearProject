"""
SignalStream — Churn Risk Worker
================================
Consumes from feedback.enriched, computes customer health score and churn propensity.
"""

from __future__ import annotations

import asyncio
from typing import Any

from workers.base import BaseWorker


class ChurnWorker(BaseWorker):
    def __init__(self) -> None:
        super().__init__(
            worker_name="churn",
            topic="feedback.enriched",
            consumer_group="cg-churn",
            dlq_topic="dlq.intelligence",
        )

    async def process_message(self, message: dict[str, Any], key: str | None = None) -> None:
        self.log.info("Calculating churn risk", customer_id=message.get("customer_id"))


def main() -> None:
    worker = ChurnWorker()
    asyncio.run(worker.start())


if __name__ == "__main__":
    main()
