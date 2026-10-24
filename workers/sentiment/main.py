"""
SignalStream — Sentiment Worker
================================
Consumes from feedback.normalized, evaluates sentiment and emotion distributions,
and produces enriched annotations.
"""

from __future__ import annotations

import asyncio
from typing import Any

from workers.base import BaseWorker


class SentimentWorker(BaseWorker):
    def __init__(self) -> None:
        super().__init__(
            worker_name="sentiment",
            topic="feedback.normalized",
            consumer_group="cg-sentiment",
            dlq_topic="dlq.intelligence",
        )

    async def process_message(self, message: dict[str, Any], key: str | None = None) -> None:
        self.log.info("Analyzing sentiment", event_id=message.get("event_id"))


def main() -> None:
    worker = SentimentWorker()
    asyncio.run(worker.start())


if __name__ == "__main__":
    main()
