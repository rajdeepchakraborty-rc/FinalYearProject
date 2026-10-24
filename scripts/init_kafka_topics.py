"""
SignalStream — Kafka Topic Initializer (Python)
=================================================
Initializes all Kafka topics using aiokafka / admin client.
"""

from __future__ import annotations

import asyncio
import os
import sys

TOPICS_CONFIG = [
    # (topic_name, num_partitions, retention_days)
    ("feedback.raw", 12, 7),
    ("feedback.normalized", 12, 7),
    ("feedback.enriched", 12, 7),
    ("sentiment.events", 6, 7),
    ("issue.events", 6, 7),
    ("trend.events", 6, 14),
    ("crisis.events", 3, 30),
    ("rootcause.events", 6, 14),
    ("demand.events", 6, 14),
    ("product.events", 6, 14),
    ("support.events", 6, 14),
    ("customer-risk.events", 6, 14),
    ("recommendation.events", 6, 30),
    ("support.ticket.created", 6, 7),
    ("support.ticket.analyzed", 6, 7),
    ("support.ticket.routed", 6, 7),
    ("support.ticket.resolved", 6, 30),
    ("alerts", 3, 30),
    ("dlq.feedback.raw", 3, 30),
    ("dlq.feedback.normalized", 3, 30),
    ("dlq.intelligence", 3, 30),
    ("retry.feedback.normalized", 6, 3),
    ("retry.intelligence", 6, 3),
]


async def main() -> None:
    from aiokafka.admin import AIOKafkaAdminClient, NewTopic
    from aiokafka.errors import TopicAlreadyExistsError

    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    replication_factor = int(os.environ.get("REPLICATION_FACTOR", "1"))

    print(f"Connecting to Kafka at {bootstrap_servers}...")
    admin = AIOKafkaAdminClient(bootstrap_servers=bootstrap_servers)
    await admin.start()

    try:
        new_topics = []
        for name, partitions, retention_days in TOPICS_CONFIG:
            retention_ms = str(retention_days * 86400000)
            topic = NewTopic(
                name=name,
                num_partitions=partitions,
                replication_factor=replication_factor,
                topic_configs={
                    "retention.ms": retention_ms,
                    "compression.type": "lz4",
                },
            )
            new_topics.append(topic)

        print(f"Creating {len(new_topics)} topics...")
        try:
            await admin.create_topics(new_topics)
            print("Successfully requested topic creation.")
        except TopicAlreadyExistsError:
            print("One or more topics already exist, continuing.")
        except Exception as e:
            print(f"Notice while creating topics: {e}")

        # List topics to verify
        topics = await admin.list_topics()
        print(f"\nCurrently configured topics ({len(topics)} total):")
        for t in sorted(topics):
            print(f"  - {t}")
    finally:
        await admin.close()


if __name__ == "__main__":
    asyncio.run(main())
