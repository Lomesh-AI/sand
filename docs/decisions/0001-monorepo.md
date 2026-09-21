# ADR 0001 — Monorepo layout for the AppSec Incident Lab

- **Status:** accepted
- **Date:** 2026-07-27
- **Deciders:** Josue Barros

## Context

The lab has three runnable services (Go API, Python worker, Next.js dashboard) plus a shared API contract, infra configs, scripts, runbooks, and incident post-mortems. We need a layout that:

- Keeps each service independently buildable and deployable.
- Makes the OpenAPI contract the single source of truth for both the Go server and the Next.js client.
- Version-controls infrastructure (Nginx, Prometheus, Grafana, OTel Collector, Tempo, RabbitMQ) alongside the code that emits/consumes telemetry.
- Fits a one-day build without an extra build-orchestration tool (Bazel, Nx, Turborepo).

## Decision

Use a **flat monorepo** with three top-level directories:

```
appsec-incident-lab/
├── apps/        # runnable services (Go, Python, Next.js)
├── packages/    # shared contracts (OpenAPI, JSON schemas, test fixtures)
├── infrastructure/  # declarative infra (Nginx, Prometheus, Grafana, OTel, Tempo, RabbitMQ)
├── scripts/     # incident-scenario shell scripts
├── docs/        # ADRs, runbooks, RCAs, architecture
```

## Consequences

Positive:
- Atomic commits touching API + consumer (e.g. contract change) are possible.
- One `Makefile` is the single entry point for every developer task.
- Onboarding: `git clone && make up` is the entire setup.

Negative:
- No enforced dependency isolation between apps (mitigated by `apps/<service>/Makefile` per service).
- CI cannot trivially cache per-service; for a one-day lab this is acceptable.

## Rejected alternatives

- **Polyrepo with shared `contracts` repo via Git submodule** — extra ceremony, no benefit at this scale.
- **Turborepo/Nx orchestration** — overkill for 3 apps; adds a build-graph layer that hides failures.
- **Single repo per service** — cannot share the OpenAPI file without symlinks or a publish step.
