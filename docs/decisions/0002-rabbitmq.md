# ADR 0002 — RabbitMQ as the asynchronous backbone

- **Status:** accepted
- **Date:** 2026-07-27
- **Deciders:** Josue Barros

## Context

The lab demonstrates at-least-once delivery, bounded retries, dead-letter routing, and poison-message handling — concepts that are far easier to teach with a real broker than with an in-memory queue. RabbitMQ is the de-facto choice for this in the AppSec/SaaS world (Snyk, Mend, GitLab Ultimate all use it).

## Decision

Use **RabbitMQ 3.13-management-alpine** with:

- One topic exchange `appsec.findings`.
- Main queue `findings.enrichment.v1` bound to `finding.created.v1`.
- Three delayed-message retry queues (`5s`, `30s`, `2m`).
- One dead-letter queue `findings.enrichment.dlq.v1`.
- One outbound processed-events queue `findings.processed.v1`.
- Persistent messages, manual acks, publisher confirms, prefetch = 8 (configurable).

## Consequences

Positive:
- `rabbitmqctl list_queues` gives an operator-grade view during incidents.
- Delayed-message exchange plugin avoids the TTL+DLX dance.
- Management UI is bundled — instant triage UX.

Negative:
- Adds ~150 MB RAM. We compensate with `mem_limit` in compose.
- Requires schema definitions pre-loaded via `definitions.json` for first-boot topology.

## Rejected alternatives

- **Kafka** — better throughput, but operationally heavier (ZooKeeper/KRaft, consumer groups, retention). Overkill for a one-day lab.
- **Redis Streams** — would also work for idempotency, but obscures the broker/consumer/DLQ mental model that the lab wants to teach.
- **NATS / in-process queue** — too thin; no DLQ semantics.
