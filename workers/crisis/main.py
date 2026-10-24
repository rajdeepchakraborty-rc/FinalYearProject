"""
SignalStream — Crisis Detection Worker
=======================================
Consumes trend & sentiment spikes to flag potential brand crises and emit alerts.
"""

from __future__ import annotations

import asyncio
from typing import Any

from workers.base import BaseWorker


class CrisisWorker(BaseWorker):
    def __init__(self) -> None:
        super().__init__(
            worker_name="crisis",
            topic="crisis.events",
            consumer_group="cg-crisis",
            dlq_topic="dlq.intelligence",
        )

    async def process_message(self, message: dict[str, Any], key: str | None = None) -> None:
        self.log.info("Evaluating crisis risk and early warnings", event_id=message.get("event_id"))


def main() -> None:
    worker = CrisisWorker()
    asyncio.run(worker.start())


if __name__ == "__main__":
    main()
