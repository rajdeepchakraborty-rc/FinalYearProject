"""
SignalStream — Ticket Routing Worker (JEV Engine)
==================================================
Consumes from support.ticket.created, evaluates routing rules and priority,
and produces to support.ticket.routed.
"""

from __future__ import annotations

import asyncio
from typing import Any

from workers.base import BaseWorker


class TicketRoutingWorker(BaseWorker):
    def __init__(self) -> None:
        super().__init__(
            worker_name="ticket_routing",
            topic="support.ticket.created",
            consumer_group="cg-ticket-routing",
            dlq_topic="dlq.intelligence",
        )

    async def process_message(self, message: dict[str, Any], key: str | None = None) -> None:
        self.log.info("Routing ticket via JEV", ticket_id=message.get("ticket_id"))


def main() -> None:
    worker = TicketRoutingWorker()
    asyncio.run(worker.start())


if __name__ == "__main__":
    main()
