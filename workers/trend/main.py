"""
SignalStream — Trend Worker
============================
Consumes from feedback.enriched, detects statistical anomalies and trending issues.
"""

from __future__ import annotations

import asyncio
from typing import Any

from workers.base import BaseWorker


class TrendWorker(BaseWorker):
    def __init__(self) -> None:
        super().__init__(
            worker_name="trend",
            topic="feedback.enriched",
            consumer_group="cg-trend",
            dlq_topic="dlq.intelligence",
        )

    async def process_message(self, message: dict[str, Any], key: str | None = None) -> None:
        self.log.info("Computing trends and rolling windows", event_id=message.get("event_id"))


def main() -> None:
    worker = TrendWorker()
    asyncio.run(worker.start())


if __name__ == "__main__":
    main()
