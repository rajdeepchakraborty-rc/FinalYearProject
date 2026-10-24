"""
SignalStream — Demand Worker
============================
Consumes from feedback.normalized, identifies customer feature requests,
willingness to pay, and product demands.
"""

from __future__ import annotations

import asyncio
from typing import Any

from workers.base import BaseWorker


class DemandWorker(BaseWorker):
    def __init__(self) -> None:
        super().__init__(
            worker_name="demand",
            topic="feedback.normalized",
            consumer_group="cg-demand",
            dlq_topic="dlq.intelligence",
        )

    async def process_message(self, message: dict[str, Any], key: str | None = None) -> None:
        self.log.info("Analyzing product demand signals", event_id=message.get("event_id"))


def main() -> None:
    worker = DemandWorker()
    asyncio.run(worker.start())


if __name__ == "__main__":
    main()
