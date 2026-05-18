# Layer 0 — Dockerized Microservices

**Status:** Complete  
**Date:** 2026-05-18

## What was built

Three microservices running via Docker Compose with health endpoints:

| Service   | Language           | Port | Image Size |
|-----------|--------------------|------|------------|
| gateway   | TypeScript/Express | 3000 | 296 MB     |
| inference | Java 21/Spring Boot| 8080 | 324 MB     |
| collector | Python 3.11/FastAPI| 8000 | 266 MB     |

## Endpoints implemented

**Gateway (port 3000):**
- `GET /health` — status, uptime, timestamp
- `GET /metrics` — Prometheus-format counters + histograms

**Inference (port 8080):**
- `GET /health` — status, uptime, timestamp
- `GET /metrics` — Prometheus-format counters + histograms
- `GET /ready` — returns 503 during chaos mode (separate from /health for k8s probes)
- `POST /predict` — simulates inference (50-200ms jitter), returns model + predictions + latency
- `POST /chaos/enable` — 50% error rate on /predict, 503 on /ready
- `POST /chaos/disable` — revert to normal
- `GET /chaos/latency?ms=N` — inject additional latency

**Collector (port 8000):**
- `GET /health` — status, uptime, timestamp (placeholder service for now)

## Design choices

**JSON envelope:** All services use `{ data, error, timestamp }` for every response. Consistent parsing across services in later layers.

**Prometheus metrics format:** Gateway and inference expose `/metrics` in Prometheus exposition format (counters + histograms with standard buckets). The collector will scrape these in Layer 2 — no need for a Prometheus server since the collector IS the monitoring.

**Chaos engineering built-in from Layer 0:** The inference service has chaos endpoints from the start rather than adding them later. This makes the /ready vs /health distinction clear early — /health always returns 200 (for k8s liveness), /ready returns 503 during chaos (for k8s readiness). This separation matters for Layer 1's k8s probes.

**Virtual threads (inference):** Spring Boot 3 with `spring.threads.virtual.enabled=true`. Each /predict request blocks a virtual thread for 50-200ms — with platform threads this would limit throughput; virtual threads handle thousands of concurrent requests without thread pool exhaustion.

**No ORM (gateway):** Using raw `pg` (node-postgres) per conventions. No ioredis or pg added yet — they come in Layers 3+.

**Docker multi-stage builds:** 
- Gateway: node:20-slim build stage (tsc), node:20-slim runtime with production deps only
- Inference: gradle:8.8-jdk21 build stage, eclipse-temurin:21-jre-alpine runtime (~324MB — JRE baseline is ~100MB, unavoidable without custom jlink)
- Collector: python:3.11-slim build stage (pip install), python:3.11-slim runtime

**Non-root users:** All containers run as `appuser`, not root.

## File structure

```
services/
  gateway/
    src/index.ts          # Express app, routes, error handling
    src/metrics.ts        # Request counting + histogram tracking
    package.json
    tsconfig.json         # strict: true
    Dockerfile
    .dockerignore
  inference/
    src/main/java/com/inference/
      InferenceApplication.java
      model/ApiResponse.java            # Generic { data, error, timestamp } record
      service/ChaosService.java         # Volatile flags for chaos state
      service/MetricsService.java       # Thread-safe counters + histogram
      controller/HealthController.java  # /health, /metrics, /ready
      controller/PredictController.java # /predict with jitter + chaos
      controller/ChaosController.java   # /chaos/* endpoints
    src/main/resources/application.yml
    build.gradle.kts
    Dockerfile
    .dockerignore
  collector/
    app/main.py           # FastAPI app, /health, startup log
    app/__init__.py
    requirements.txt
    Dockerfile
    .dockerignore
docker-compose.yml        # All three services + shared bridge network
```

## Verification

```
$ docker compose up -d
$ curl localhost:3000/health  → 200 { status: "healthy", uptime: 76.7 }
$ curl localhost:8080/health  → 200 { status: "healthy", uptime: 80913 }
$ curl localhost:8000/health  → 200 { status: "healthy", uptime: 81.8 }
$ curl -X POST localhost:8080/predict → 200 { model: "inference-v1", predictions: [...], latency_ms: 192 }
$ curl localhost:3000/metrics → Prometheus format with counters + histograms
$ curl -X POST localhost:8080/chaos/enable → chaos mode on
$ curl localhost:8080/ready → 503 (chaos active)
$ curl -X POST localhost:8080/chaos/disable → chaos mode off
```

## Next: Layer 1 — Kubernetes deployment
- k8s manifests for all three services (Deployment, Service, Ingress)
- Readiness probes on /health (gateway, collector) and /ready (inference)
- Liveness probes on /health for all
- Ingress routing /api/* → gateway, /inference/* → inference
