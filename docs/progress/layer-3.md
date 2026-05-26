# Layer 3 — Redis + Dashboard API

**Status:** Complete  
**Date:** 2026-05-25

## What I did

1. Wrote a plain Kubernetes manifest for Redis (`k8s/redis/redis.yaml`) using the official `redis:7-alpine` image — same approach as Kafka, avoiding the bitnami paywall. Configured as a StatefulSet with 1Gi persistent storage, non-root user (uid 999), and append-only persistence.
2. Updated the collector (`services/collector/app/main.py`) to write current service state to Redis after each scrape cycle. Four keys per service: `service:{name}:status`, `service:{name}:p95`, `service:{name}:error_rate`, `service:{name}:last_check`. Redis connection failure is handled gracefully — scraping continues without caching.
3. Added dashboard endpoints to the gateway (`services/gateway/src/dashboard.ts`):
   - `GET /api/services/status` — reads live status from Redis for all services
   - `GET /api/services/:name/history?range=1h|6h|24h|7d` — queries PostgreSQL health_checks
   - `GET /api/incidents` — queries PostgreSQL incidents (limit 50)
   - `GET /api/incidents/active` — queries incidents where resolved_at IS NULL
4. Added `ioredis` and `pg` as gateway dependencies. Created Redis and PostgreSQL clients in `index.ts`, injected into the dashboard router via a factory function.
5. Created a `shared-config` ConfigMap with `REDIS_URL` and `DATABASE_URL`, referenced by both gateway and collector via `envFrom`. Kept `collector-config` for collector-specific env vars (Kafka, service URLs).
6. Rebuilt and pushed gateway + collector images, deployed to GKE, verified all endpoints return correct data.

## What was built

Live dashboard API backed by Redis (real-time) and PostgreSQL (historical).

| Resource | File | Details |
|----------|------|---------|
| Redis StatefulSet + Services | `k8s/redis/redis.yaml` | `redis:7-alpine`, 1Gi PVC, non-root |
| Dashboard router | `services/gateway/src/dashboard.ts` | 4 endpoints, Redis + PostgreSQL queries |
| Updated gateway | `services/gateway/src/index.ts` | Redis + pg clients, dashboard mount |
| Updated collector | `services/collector/app/main.py` | Redis writes after each scrape |
| Shared ConfigMap | `k8s/base/configmap.yaml` | REDIS_URL + DATABASE_URL for gateway and collector |

## Design choices

**Factory function for router:** The dashboard router takes Redis and pg pool as constructor parameters rather than importing globals. This keeps the router testable and makes dependencies explicit.

**Shared ConfigMap:** Both gateway and collector need REDIS_URL and DATABASE_URL. Rather than duplicating values, a `shared-config` ConfigMap is referenced by both deployments. Collector-specific config (Kafka, service URLs) stays in `collector-config`.

**Redis key pattern (`service:{name}:*`):** Flat key structure with scan-by-prefix. Simple and fast for a small number of services. The gateway discovers services dynamically by scanning `service:*:status` keys — no hardcoded service list.

**Range-to-interval mapping:** History endpoint accepts human-readable ranges (1h, 6h, 24h, 7d) and maps them to PostgreSQL intervals. Invalid ranges return 400 with a helpful error message.

## Verification

```
$ curl http://localhost:3000/api/services/status
{
  "data": [
    { "name": "inference", "status": "healthy", "latency_p95_ms": 0, "error_rate": 0, "last_check": "2026-05-26T02:51:18.033105+00:00" },
    { "name": "gateway", "status": "healthy", "latency_p95_ms": 50, "error_rate": 0, "last_check": "2026-05-26T02:51:18.032282+00:00" }
  ],
  "error": null,
  "timestamp": "2026-05-26T02:51:25.002Z"
}

$ curl "http://localhost:3000/api/services/gateway/history?range=1h"
→ 1000+ health_check rows with raw_metrics JSONB

$ curl http://localhost:3000/api/incidents/active
→ { "data": [], "error": null } (no incidents yet — expected)
```

## Next: Layer 4 — Incident Detection + Chaos
- Threshold-based alerting in collector (error_rate > 0.05, p95 > 500ms)
- Chaos injection on inference triggers automatic incident creation
- Demo script for end-to-end chaos → incident flow
