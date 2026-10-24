#!/usr/bin/env bash
# =============================================================
# SignalStream — Kafka Topics Initialization Script
# =============================================================
# Creates all required Kafka topics with defined partitions and retention ms.
# Usage:
#   docker exec -i signalstream-kafka /bin/bash < scripts/init_kafka_topics.sh
#   OR run locally against KAFKA_BOOTSTRAP_SERVERS

set -euo pipefail

BOOTSTRAP_SERVER="${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"
KAFKA_BIN="/opt/kafka/bin"

if ! command -v kafka-topics.sh &> /dev/null; then
    if [ -d "$KAFKA_BIN" ]; then
        export PATH="$KAFKA_BIN:$PATH"
    fi
fi

echo "Connecting to Kafka at: ${BOOTSTRAP_SERVER}"

# Helper function
create_topic() {
    local topic=$1
    local partitions=$2
    local retention_days=$3
    local retention_ms=$((retention_days * 86400000))
    local replication_factor="${REPLICATION_FACTOR:-1}"

    echo "Creating topic: ${topic} (partitions=${partitions}, retention=${retention_days}d)..."
    kafka-topics.sh --bootstrap-server "${BOOTSTRAP_SERVER}" \
        --create --if-not-exists \
        --topic "${topic}" \
        --partitions "${partitions}" \
        --replication-factor "${replication_factor}" \
        --config retention.ms="${retention_ms}" \
        --config compression.type=lz4 || true
}

# ── Primary Pipeline Topics ──────────────────────────────────
create_topic "feedback.raw" 12 7
create_topic "feedback.normalized" 12 7
create_topic "feedback.enriched" 12 7
create_topic "sentiment.events" 6 7
create_topic "issue.events" 6 7
create_topic "trend.events" 6 14
create_topic "crisis.events" 3 30
create_topic "rootcause.events" 6 14
create_topic "demand.events" 6 14
create_topic "product.events" 6 14
create_topic "support.events" 6 14
create_topic "customer-risk.events" 6 14
create_topic "recommendation.events" 6 30
create_topic "support.ticket.created" 6 7
create_topic "support.ticket.analyzed" 6 7
create_topic "support.ticket.routed" 6 7
create_topic "support.ticket.resolved" 6 30
create_topic "alerts" 3 30

# ── Dead Letter Queues (DLQ) ─────────────────────────────────
create_topic "dlq.feedback.raw" 3 30
create_topic "dlq.feedback.normalized" 3 30
create_topic "dlq.intelligence" 3 30

# ── Retry Topics ─────────────────────────────────────────────
create_topic "retry.feedback.normalized" 6 3
create_topic "retry.intelligence" 6 3

echo "All SignalStream Kafka topics created successfully!"
