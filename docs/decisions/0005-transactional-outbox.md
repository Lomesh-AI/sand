# ADR-0005: Transactional Outbox for Finding-Created Events

**Status:** Accepted  
**Date:** 2026-07-28  
**Author:** Josue Barros  
**Scope:** findings-api (Go), enrichment-worker (Python)

## Context

When the API receives a `POST /api/v1/findings`, two things must happen atomically:

1. The finding document is persisted to MongoDB.
2. A `finding.created.v1` event is published to RabbitMQ so the enrichment worker can process it.

If we write to MongoDB and then publish to RabbitMQ as two separate operations, we have a **dual-write problem**:

- **Mongo succeeds, RabbitMQ fails** → finding exists but no one processes it (silent data loss).
- **RabbitMQ succeeds, Mongo fails** → worker processes a ghost event (orphan message).
- **Process crashes between the two** → indeterminate state, requires manual reconciliation.

In a distributed system without 2PC/XA, we need a pattern that guarantees *at-least-once* delivery without sacrificing data consistency.

## Decision

We adopt the **Transactional Outbox** pattern:

1. The API writes the finding document **and** an outbox message into MongoDB in the **same transaction** (same `InsertOne` on a single document for now; future: multi-document ACID transaction).
2. A background publisher goroutine polls the `outbox_messages` collection, claims un-published rows, publishes them to RabbitMQ with publisher confirms, and marks them as published.
3. The enrichment worker consumes from RabbitMQ, enriches the finding, and writes the result back to MongoDB.

## Consequences

### Positive

- **Consistency**: The finding and the event are always in sync because they live in the same MongoDB document (or same transaction boundary).
- **Reliability**: Publisher confirms + idempotency key ensure at-least-once delivery without duplicates.
- **Observability**: The outbox table is queryable; we can monitor lag, retry counts, and dead letters.
- **Decoupling**: The API does not block on RabbitMQ availability; messages are queued locally.

### Negative

- **Latency**: There is a small delay (≤ 1s with current polling interval) between MongoDB write and RabbitMQ delivery.
- **Operational complexity**: We must run the publisher goroutine and monitor the outbox table.
- **Storage growth**: Published outbox rows are not deleted (intentionally, for audit); a TTL index or compaction job may be needed in production.

## Alternatives Considered

| Approach | Why Rejected |
|----------|--------------|
| Direct RabbitMQ publish after Mongo insert | Dual-write risk; no recovery if publish fails. |
| MongoDB Change Streams → RabbitMQ | Adds another moving part (Change Stream consumer); harder to guarantee ordering and delivery semantics. |
| Saga / 2PC | Overkill for a single-document write; requires XA coordinator. |
| In-memory outbox (channel) | Lost on process restart; violates durability. |

## Implementation Notes

- Collection: `outbox_messages`
- Polling interval: 1s (configurable via `OUTBOX_POLL_EVERY`)
- Batch size: 50 messages per cycle (`OUTBOX_BATCH_SIZE`)
- Publisher confirms: enabled on the RabbitMQ channel
- Idempotency: `Idempotency-Key` header + Redis cache + MongoDB unique index on `(tenant_id, scanner, external_id)`

## Related Decisions

- [ADR-0003: Idempotency Strategy](0003-idempotency.md)
- [ADR-0002: RabbitMQ Topology](0002-rabbitmq.md)
