"""
SignalStream — Root Cause Worker
=================================
Consumes from feedback.enriched, performs semantic clustering and causal analysis.
"""

from __future__ import annotations

import asyncio
from typing import Any

from workers.base import BaseWorker


class RootCauseWorker(BaseWorker):
    def __init__(self) -> None:
        super().__init__(
            worker_name="rootcause",
            topic="feedback.enriched",
            consumer_group="cg-rootcause",
            dlq_topic="dlq.intelligence",
        )

    async def process_message(self, message: dict[str, Any], key: str | None = None) -> None:
        self.log.info("Analyzing root causes", event_id=message.get("event_id"))


def main() -> None:
    worker = RootCauseWorker()
    asyncio.run(worker.start())


if __name__ == "__main__":
    main()
