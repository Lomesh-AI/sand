# ADR 0004 — Three pillars, one collector, two backends

- **Status:** accepted
- **Date:** 2026-07-27
- **Deciders:** Josue Barros

## Context

The lab must teach real SRE/Ops workflows: metrics for alerts, traces for incident investigation, logs for context. We need to do this without the operational cost of a vendor (Datadog, New Relic) or a 10-service toolchain.

## Decision

Standardize on **OpenTelemetry as the telemetry API**, with a **single OpenTelemetry Collector** as the OTLP receiver. The collector fans out to:

- **Tempo** — trace storage; queried from Grafana via TraceQL.
- **Prometheus** — metrics scrape target (`otel-collector` exposes a Prometheus endpoint).

Application logging uses native structured JSON (zap in Go, structlog in Python). Logs are not shipped through OTel in this lab — they are read via `docker compose logs` and via Loki would be the production move.

## Consequences

Positive:
- Applications speak one telemetry API (OTel) regardless of backend.
- Grafana becomes the single pane of glass (Prometheus + Tempo).
- Demonstrates the **collector ≠ backend** distinction that confuses junior engineers.

Negative:
- One extra hop (app → collector → backend). Negligible latency.
- Logs and traces are correlated by `trace_id` only if both are present; we inject the trace context into every log line.

## Rejected alternatives

- **Push metrics directly to Prometheus pushgateway** — pushes vs pulls; loses Prometheus' service-discovery story.
- **Vendor SaaS (Datadog/Honeycomb)** — needs an account + cost.
- **Tempo + Loki + Mimir** — heavier than one day allows and Loki is not in the brief.
