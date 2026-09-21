# AppSec Incident Lab — Security Hardening Guide

## Overview

This document describes the security controls built into the AppSec Incident Lab
and provides a checklist for production hardening.

## Current Security Controls

### Authentication

| Layer | Implementation | Notes |
|-------|---------------|-------|
| JWT | HS256 with `golang-jwt/jwt/v5` | Short-lived tokens (1h default), `iss`/`sub`/`exp`/`tenant_id`/`scope` claims |
| API Key | SHA-256 constant-time comparison | Fallback for admin/scripts; rotates via env var |
| Tenant Isolation | Every query scoped to `tenant_id` | Prevents cross-tenant data leakage |

### Authorization

- `findings:write` scope required for POST /findings
- `findings:read` scope required for GET /findings
- `admin:scenarios` scope required for admin endpoints
- Tenant mismatch between JWT claim and body → 401

### Input Validation

- `go-playground/validator/v10` with struct tags
- Severity enum: `critical`, `high`, `medium`, `low`, `informational`
- Environment enum: `dev`, `staging`, `prod`
- CVSS clamped to [0, 10]
- Title/description length limits
- JSON body size limited by server (default ~1MB)

### Idempotency & Abuse Prevention

- `Idempotency-Key` header prevents duplicate processing
- Redis TTL (24h) prevents indefinite key accumulation
- MongoDB unique index on `(tenant_id, scanner, external_id)` is the source of truth

### Container Security

| Control | Implementation |
|---------|---------------|
| Non-root user | `USER nonroot:nonroot` in distroless images |
| Minimal base image | `gcr.io/distroless/static-debian12:nonroot` |
| No shell | Distroless has no bash/sh — reduces attack surface |
| Read-only filesystem | Could be added with `readOnlyRootFilesystem: true` |
| Resource limits | Memory/CPU limits in K8s manifests |
| No capabilities | Default drop-all in K8s securityContext |

### Network Security

- Nginx adds security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `X-XSS-Protection`
- Internal services communicate via Docker/K8s private networks
- No external exposure of MongoDB, Redis, or RabbitMQ

### Secrets Management

- Secrets loaded from environment variables (12-factor)
- `.env.example` documents required variables
- `.env` is `.gitignore`d
- K8s uses `Secret` resources (base64 — upgrade to external-secrets/Vault in prod)

### Observability & Audit

- Structured JSON logs with correlation IDs
- OpenTelemetry traces across all services
- Prometheus metrics for anomaly detection
- All admin actions logged with tenant_id and user context

## Production Hardening Checklist

### Infrastructure

- [ ] Replace HS256 JWT with RS256 (asymmetric) or OIDC
- [ ] Add rate limiting per tenant (Redis-backed token bucket)
- [ ] Enable TLS 1.3 on all ingress points
- [ ] Add mTLS between internal services (Istio/Linkerd)
- [ ] Deploy WAF (Cloudflare/AWS WAF) in front of Nginx
- [ ] Add DDoS protection at edge

### Secrets

- [ ] Migrate from env vars to HashiCorp Vault / AWS Secrets Manager
- [ ] Use `external-secrets` operator in K8s
- [ ] Rotate JWT signing keys quarterly
- [ ] Rotate API keys monthly
- [ ] Encrypt secrets at rest (K8s etcd encryption)

### Database

- [ ] Enable MongoDB TLS
- [ ] Enable MongoDB authentication (SCRAM-SHA-256)
- [ ] Enable MongoDB audit logging
- [ ] Add MongoDB backup (point-in-time)
- [ ] Enable Redis TLS
- [ ] Enable Redis ACL (separate users per service)

### Messaging

- [ ] Enable RabbitMQ TLS (AMQPS)
- [ ] Enable RabbitMQ auth with least-privilege users
- [ ] Add RabbitMQ queue quotas to prevent DoS
- [ ] Enable RabbitMQ audit logging

### API Security

- [ ] Add request size limits (already ~1MB)
- [ ] Add request timeout (already 30s default)
- [ ] Add CORS whitelist
- [ ] Add Content Security Policy headers
- [ ] Add HSTS header (requires TLS)
- [ ] Implement API versioning strategy
- [ ] Add deprecation warnings for old versions

### Container & Runtime

- [ ] Enable seccomp profiles
- [ ] Enable AppArmor/SELinux
- [ ] Add `readOnlyRootFilesystem: true` in K8s
- [ ] Add `allowPrivilegeEscalation: false`
- [ ] Add `runAsNonRoot: true`
- [ ] Scan images with Trivy/Snyk in CI
- [ ] Sign images with Cosign

### Monitoring & Alerting

- [ ] Alert on high error rate (>5%)
- [ ] Alert on high conflict rate (>10%)
- [ ] Alert on dependency health = 0
- [ ] Alert on DLQ depth > 100
- [ ] Alert on JWT auth failure rate > 1%
- [ ] Alert on unusual tenant activity (anomaly detection)

### Compliance

- [ ] SOC 2 Type II audit trail
- [ ] GDPR data retention policies
- [ ] Data classification (PII in findings?)
- [ ] Incident response playbook
- [ ] Penetration testing (quarterly)

## Threat Model

| Threat | Likelihood | Impact | Mitigation |
|--------|-----------|--------|------------|
| JWT theft | Medium | High | Short TTL, RS256, rotation |
| Replay attack | Low | Medium | Idempotency keys, unique index |
| Tenant isolation breach | Low | Critical | Tenant scoping on every query |
| MongoDB injection | Low | High | Parameterized queries, validation |
| DoS via large payloads | Medium | Medium | Size limits, rate limiting |
| Container escape | Low | Critical | Distroless, non-root, seccomp |
| Secret leakage | Medium | High | Vault, encryption, rotation |
| Insider threat | Medium | High | Audit logs, least privilege |

## References

- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [NIST SP 800-190](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-190.pdf)
