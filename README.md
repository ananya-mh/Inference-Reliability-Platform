# AI Inference Reliability Platform

A Datadog-lite observability and incident detection system for distributed inference workloads. Scrapes metrics, detects anomalies, auto-creates and resolves incidents, and serves a live dashboard API.

## Architecture

```
gateway (TypeScript/Express)     inference (Java/Spring Boot)
       │                                  │
       └──── /metrics ────┐  ┌── /metrics ┘
                          ▼  ▼
                  collector (Python/FastAPI)
                     │    │    │
                     ▼    ▼    ▼
                  Kafka  Redis  Detector
                    │      │       │
                    ▼      │       ▼
               PostgreSQL  │   Kafka (incidents)
                    │      │       │
                    ▼      ▼       ▼
              Gateway Dashboard API ◄── PostgreSQL
              /api/services/status  (Redis - live)
              /api/services/:name/history (PostgreSQL - historical)
              /api/incidents (PostgreSQL)
```

### Services

| Service | Language | Port | Role |
|---------|----------|------|------|
| gateway | TypeScript / Express | 3000 | Request intake, Prometheus metrics, dashboard API |
| inference | Java 21 / Spring Boot | 8080 | Model serving simulator, chaos injection endpoints |
| collector | Python / FastAPI | 8000 | Metrics scraping, Kafka streaming, incident detection |

### Infrastructure

| Component | Image | Purpose |
|-----------|-------|---------|
| Kafka | apache/kafka:3.9.0 | Event streaming (KRaft mode, no ZooKeeper) |
| PostgreSQL | bitnami/postgresql | Historical metrics and incident storage |
| Redis | redis:7-alpine | Live service state cache |

## Quick Start — Local (Docker Compose)

```bash
docker compose up --build
```

Services available at `localhost:3000`, `localhost:8080`, `localhost:8000`. No Kafka/Redis/PostgreSQL in compose — local mode runs health endpoints only.

## Deploy to GKE

### Prerequisites
- `gcloud` CLI authenticated
- GKE Autopilot cluster created
- Artifact Registry repo created
- `kubectl` connected to cluster
- Helm installed

### 1. Build and push images

```bash
# Set your project/region
PROJECT=ai-inference-497423
REGION=us-south1
REPO=inference-repo
REGISTRY=$REGION-docker.pkg.dev/$PROJECT/$REPO

# Configure Docker auth
gcloud auth configure-docker $REGION-docker.pkg.dev

# Build and push all three
for svc in gateway inference collector; do
  docker build -t $REGISTRY/$svc:latest services/$svc
  docker push $REGISTRY/$svc:latest
done
```

### 2. Deploy infrastructure

```bash
# PostgreSQL
helm install postgresql bitnami/postgresql -f k8s/postgresql/values.yaml

# Apply schema
kubectl exec -i postgresql-0 -- env PGPASSWORD=postgres \
  psql -U postgres -d inference_platform < k8s/postgresql/schema.sql

# Kafka + Redis
kubectl apply -f k8s/kafka/kafka.yaml
kubectl apply -f k8s/redis/redis.yaml

# Wait for infrastructure
kubectl get pods -w  # wait until all Running
```

### 3. Deploy application

```bash
kubectl apply -f k8s/base/configmap.yaml
kubectl apply -f k8s/base/gateway.yaml
kubectl apply -f k8s/base/inference.yaml
kubectl apply -f k8s/base/collector.yaml
```

### 4. Verify

```bash
# All pods running
kubectl get pods

# Port-forward to test
kubectl port-forward svc/gateway 3000:3000

# Live service status (from Redis)
curl http://localhost:3000/api/services/status

# Historical data (from PostgreSQL)
curl "http://localhost:3000/api/services/gateway/history?range=1h"

# Active incidents
curl http://localhost:3000/api/incidents/active
```

## Dashboard API

| Endpoint | Source | Description |
|----------|--------|-------------|
| `GET /api/services/status` | Redis | Live status of all services |
| `GET /api/services/:name/history?range=1h` | PostgreSQL | Historical health checks (1h, 6h, 24h, 7d) |
| `GET /api/incidents` | PostgreSQL | All incidents, newest first (limit 50) |
| `GET /api/incidents/active` | PostgreSQL | Unresolved incidents |

All endpoints return `{ data, error, timestamp }`.

## Chaos Testing

The inference service supports fault injection:

```bash
# Enable chaos (50% errors on /predict, 503 on /ready)
kubectl exec <inference-pod> -- wget -qO- --post-data="" http://localhost:8080/chaos/enable

# Add artificial latency
kubectl exec <inference-pod> -- wget -qO- http://localhost:8080/chaos/latency?ms=800

# Disable
kubectl exec <inference-pod> -- wget -qO- --post-data="" http://localhost:8080/chaos/disable
```

Or run the full demo:
```bash
bash scripts/demo-chaos.sh
```

The collector detects sustained failures within ~20 seconds and auto-creates incidents. When the service recovers, incidents are auto-resolved.

## Incident Detection Rules

| Rule | Threshold | Sustained | Incident Type |
|------|-----------|-----------|---------------|
| High error rate | > 5% | 2+ checks (20s) | `high_error_rate` |
| High latency | p95 > 500ms | 2+ checks (20s) | `high_latency` |
| Service down | Unreachable | 2+ checks (20s) | `high_error_rate` |

## Project Structure

```
services/
  gateway/          TypeScript/Express — dashboard API, Prometheus metrics
  inference/        Java 21/Spring Boot — model simulator, chaos endpoints
  collector/        Python/FastAPI — scraper, Kafka producer/consumer, detector
k8s/
  base/             Service deployments, ConfigMaps, Ingress
  kafka/            Kafka StatefulSet (apache/kafka, KRaft)
  redis/            Redis StatefulSet
  postgresql/       Helm values + SQL schema
scripts/
  demo-chaos.sh     End-to-end chaos injection demo
docs/
  progress/         Layer-by-layer build progress files
  interview-prep.md Detailed interview preparation guide
```

## Build Layers

| Layer | What | Status |
|-------|------|--------|
| 0 | Dockerized microservices with health endpoints |
| 1 | Kubernetes deployment with probes and Ingress | 
| 2 | Kafka + PostgreSQL metrics streaming pipeline | 
| 3 | Redis live state + dashboard API | 
| 4 | Incident detection + chaos testing |
| 5 | Cascading failure detection + LLM root-cause + HPA | 

## Cleanup

```bash
# Delete application
kubectl delete -f k8s/base/

# Delete infrastructure
kubectl delete -f k8s/kafka/kafka.yaml
kubectl delete -f k8s/redis/redis.yaml
helm uninstall postgresql

# Delete PVCs
kubectl delete pvc --all

# Delete GKE cluster (stops billing)
gcloud container clusters delete inference-cluster --region us-south1
```
