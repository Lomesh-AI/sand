# AppSec Incident Lab — On-Call Runbook

## PagerDuty Alert: API Error Rate > 5%

### Symptoms
- Prometheus alert: `findings_api_http_requests_total{status=~"5.."} / findings_api_http_requests_total > 0.05`
- Dashboard shows red error rate spike
- Users reporting 500 errors

### Diagnosis

```bash
# 1. Check API health
./scripts/wait-for-services.sh

# 2. Check recent logs
docker compose logs --tail=100 findings-api

# 3. Check dependency health
curl http://localhost:8081/health/ready

# 4. Check MongoDB
docker compose exec mongodb mongosh --quiet --eval "db.adminCommand('ping').ok"

# 5. Check Redis
docker compose exec redis redis-cli -a redis_dev_only ping

# 6. Check RabbitMQ
curl -s -u appsec:appsec_dev_only http://localhost:15673/api/healthchecks/node
```

### Common Causes

| Cause | Evidence | Fix |
|-------|----------|-----|
| MongoDB down | `health/ready` = 503, Mongo check = down | `docker compose restart mongodb` |
| Redis down | `health/ready` = 503, Redis check = down | `docker compose restart redis` |
| RabbitMQ down | `health/ready` = 503, Rabbit check = down | `docker compose restart rabbitmq` |
| Outbox backlog | `findings_api_outbox_messages_total` > 1000 | Check RabbitMQ connectivity |
| Memory leak | Container memory > limit | Restart container, check for goroutine leak |

### Escalation
- If restart doesn't fix → check disk space: `df -h`
- If disk full → `docker system prune -f` (careful)
- If still failing → page SRE team

---

## PagerDuty Alert: Worker Dead-Lettered Messages > 100

### Symptoms
- Prometheus alert: `worker_messages_dead_lettered_total > 100`
- DLQ depth increasing
- Findings stuck in `queued` or `processing`

### Diagnosis

```bash
# 1. Check DLQ depth
curl -s -u appsec:appsec_dev_only http://localhost:15673/api/queues/%2f/findings.enrichment.dlq.v1 | jq '.messages'

# 2. Check worker logs
docker compose logs --tail=200 enrichment-worker

# 3. Check worker health
curl http://localhost:8082/health

# 4. Check MongoDB for stuck findings
docker compose exec mongodb mongosh --quiet --eval "
  db = db.getSiblingDB('appsec');
  db.findings.find({processing_status: 'queued'}).count();
"
```

### Common Causes

| Cause | Evidence | Fix |
|-------|----------|-----|
| Worker down | Health check fails | `docker compose restart enrichment-worker` |
| MongoDB slow | Worker logs show "server selection timeout" | Check MongoDB CPU/memory |
| Schema mismatch | Worker logs show "unsupported schema version" | Check `schema_version` compatibility |
| Poison messages | Worker logs show JSON decode errors | Run `./scripts/poison-message.sh` to verify DLQ behavior |

### Recovery

```bash
# Restart worker
docker compose restart enrichment-worker

# If messages are valid but stuck, requeue from DLQ
# (Manual operation — use RabbitMQ Management UI)
```

---

## PagerDuty Alert: Idempotency Conflict Rate > 10%

### Symptoms
- Prometheus alert: `rate(findings_api_findings_duplicate_total{reason="conflict"}[5m]) > 0.1`
- 409 errors spiking
- Client complaints about rejected requests

### Diagnosis

```bash
# 1. Check recent 409s
docker compose logs --tail=100 findings-api | grep "idempotency conflict"

# 2. Check Redis for key accumulation
docker compose exec redis redis-cli -a redis_dev_only info keyspace

# 3. Check if clients are reusing keys incorrectly
# Look for patterns in logs: same key, different payload
```

### Common Causes

| Cause | Evidence | Fix |
|-------|----------|-----|
| Client bug | Same `Idempotency-Key` with different payloads | Contact client team, fix key generation |
| Key collision | UUID collision (extremely rare) | Add entropy to key generation |
| Redis eviction | Keys evicted before TTL | Increase Redis memory or reduce TTL |

---

## PagerDuty Alert: Dependency Health = 0

### Symptoms
- Prometheus alert: `findings_api_dependency_health == 0`
- `health/ready` returning 503

### Quick Recovery

```bash
# Restart all infrastructure
docker compose restart mongodb redis rabbitmq

# Wait for health
sleep 10
./scripts/wait-for-services.sh

# Verify
curl http://localhost:8081/health/ready
```

---

## PagerDuty Alert: Dashboard 500 Errors

### Symptoms
- Users can't load dashboard
- Next.js error page

### Diagnosis

```bash
# 1. Check dashboard container
docker compose logs --tail=50 dashboard

# 2. Check API health (dashboard proxies to API)
curl http://localhost:8081/health/live

# 3. Check if API is reachable from dashboard container
docker compose exec dashboard wget -qO- http://findings-api:8080/health/live
```

### Common Causes

| Cause | Evidence | Fix |
|-------|----------|-----|
| API down | Dashboard logs show connection refused | Fix API first |
| Dashboard crash | Container restarting | `docker compose restart dashboard` |
| Memory limit | OOMKilled in `docker compose ps` | Increase memory limit in compose |

---

## Post-Incident Actions

1. **Document** in incident tracker:
   - Start time, end time
   - Root cause
   - Actions taken
   - Lessons learned

2. **Update** runbook if new pattern discovered

3. **Review** Grafana dashboard for anomalies

4. **Run** smoke test to verify full recovery:
   ```bash
   ./scripts/smoke-test.sh
   ```

---

## Emergency Contacts

| Role | Contact | Escalation |
|------|---------|------------|
| Primary On-Call | You | — |
| SRE Team | #sre-oncall | After 30 min if unresolved |
| Security Team | #security-oncall | If security incident suspected |
| Engineering Manager | Manager | After 1 hour if unresolved |

## Useful Commands

```bash
# Full stack restart (nuclear option)
docker compose down -v && docker compose up -d

# View all container statuses
docker compose ps

# Resource usage
docker stats --no-stream

# Network connectivity between containers
docker compose exec findings-api wget -qO- http://mongodb:27017

# MongoDB shell
docker compose exec mongodb mongosh -u appsec -p appsec_dev_only --authenticationDatabase admin appsec

# RabbitMQ management (browser)
open http://localhost:15673

# Grafana (browser)
open http://localhost:3001
```
