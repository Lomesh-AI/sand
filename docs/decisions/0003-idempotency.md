# ADR 0003 — Three-layer idempotency

- **Status:** accepted
- **Date:** 2026-07-27
- **Deciders:** Josue Barros

## Context

An AppSec scanner or CI pipeline retries POST `/api/v1/findings` after a network timeout. The API may have already persisted the finding and published the event. Without protection, the same finding ends up twice.

We also need to handle:

- Replays of the same RabbitMQ message after a consumer crash (at-least-once delivery).
- A bulk import that sends the same `(tenant, scanner, external_id)` twice.

## Decision

Three independent layers:

1. **Idempotency-Key (HTTP)** — Redis stores `{key, tenant_id, payload_hash, resource_id, status, expires_at}`. Same key + same payload → return the existing resource. Same key + different payload → 409 conflict.
2. **Unique index (Mongo)** — `findings` collection has a unique index on `(tenant_id, scanner, external_id)`. Duplicate insert returns `E11000`; the handler converts it to the existing record.
3. **Worker-side idempotence** — The worker only updates a finding if its current `processing_version` matches the message version (optimistic concurrency). Replayed messages with a stale version are acked without effect.

## Consequences

Positive:
- Each layer catches a different failure mode (replay, race, reprocess).
- The unique index is the ultimate safety net even if Redis is down.

Negative:
- Two round-trips on duplicate paths (Redis then Mongo). Acceptable for this scale.
- Worker-side version check requires a `processing_version` field on every update; we add it.

## Rejected alternatives

- **Single Redis SETNX with 24h TTL** — single point of failure for ingestion.
- **Mongo-only unique index** — does not protect against HTTP-level replays that include minor payload diffs.
- **Dedup window in the worker only** — leaves the API free to create duplicates that propagate downstream.
