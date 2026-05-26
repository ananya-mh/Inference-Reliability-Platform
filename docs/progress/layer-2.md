# Layer 2 — Kafka + Metrics Streaming

**Status:** Complete  
**Date:** 2026-05-25

## What I did

1. Wrote Kafka and PostgreSQL Helm values files for bitnami charts. Discovered bitnami moved Kafka images to a paid registry (Aug 2025), so the Helm chart couldn't pull images on GKE.
2. Pivoted to a plain Kubernetes manifest (`k8s/kafka/kafka.yaml`) using the official `apache/kafka:3.9.0` image in KRaft mode (no ZooKeeper). Configured a single combined broker+controller node. Debugged a crash-loop caused by `0.0.0.0` in `KAFKA_LISTENERS` — the apache/kafka wrapper rejects non-routable addresses, fixed by using `PLAINTEXT://:9092`.
3. Deployed PostgreSQL via bitnami Helm chart (the PostgreSQL `:latest` tag still works on Docker Hub). Applied the schema (health_checks + incidents tables with indexes) via `kubectl exec psql`.
4. Added a Kafka topic-init Job that creates `metrics.health` (3 partitions) and `metrics.incidents` (1 partition) on startup.
5. Built the collector's scraping pipeline: async HTTP calls to `/metrics` endpoints every 10s, Prometheus text parsing, p95 latency computation from histogram buckets, error rate from 5xx/total counters.
6. Built Kafka producer (`publisher.py`) and consumer (`consumer.py`) in the collector. Consumer reads from `metrics.health` and writes to PostgreSQL. Added retry loop for consumer thread startup and DB reconnection logic for dropped connections.
7. Created a ConfigMap (`collector-config`) with service URLs, Kafka bootstrap servers, and PostgreSQL DSN. Wired it into the collector Deployment via `envFrom`.
8. Migrated the entire stack from local Minikube to GKE Autopilot on GCP (project `ai-inference-497423`, region `us-south1`) — pushed images to Artifact Registry, updated manifests with full image paths.

## What was built

End-to-end metrics pipeline: scrape → publish → consume → store.

| Resource | File | Details |
|----------|------|---------|
| Kafka StatefulSet + Services | `k8s/kafka/kafka.yaml` | Single KRaft broker, `apache/kafka:3.9.0` |
| Topic init Job | `k8s/kafka/kafka.yaml` | Creates metrics.health + metrics.incidents |
| PostgreSQL | Helm `bitnami/postgresql` | `k8s/postgresql/values.yaml`, password: postgres |
| DB Schema | `k8s/postgresql/schema.sql` | health_checks + incidents tables |
| ConfigMap | `k8s/base/configmap.yaml` | GATEWAY_URL, INFERENCE_URL, KAFKA_BOOTSTRAP_SERVERS, DATABASE_URL |
| Scraper | `services/collector/app/scraper.py` | Async scraping, Prometheus parsing, p95 + error rate |
| Publisher | `services/collector/app/publisher.py` | confluent-kafka producer → metrics.health topic |
| Consumer | `services/collector/app/consumer.py` | confluent-kafka consumer → PostgreSQL inserts |
| Updated collector | `services/collector/app/main.py` | Scrape loop + consumer thread with retry |

## Design choices

**apache/kafka instead of bitnami Helm:** Bitnami moved container images behind a paid registry in Aug 2025. The official `apache/kafka` image works with KRaft out of the box and is freely available. Trade-off: no Helm templating, but a single-broker dev setup doesn't need it.

**KRaft mode (no ZooKeeper):** Kafka 3.9 supports KRaft natively — the broker manages its own metadata. Eliminates a whole ZooKeeper StatefulSet, saving ~500MB RAM on the cluster.

**Prometheus text parsing vs JSON metrics:** Gateway and inference expose Prometheus-format `/metrics` (histograms + counters). The collector parses this text format directly rather than adding a second JSON metrics endpoint. Standard format, works with any future Prometheus-compatible tooling.

**p95 from histogram buckets:** Computed by linear interpolation across histogram bucket boundaries. Not perfectly accurate (depends on bucket granularity) but good enough for alerting thresholds without requiring a full metrics library.

**Consumer retry loop:** The consumer thread connects to both Kafka and PostgreSQL on startup. If either isn't ready, it retries every 5 seconds. Also handles mid-operation DB disconnects with a `_reconnect_db()` method — catches `psycopg2.OperationalError` separately from other exceptions.

**GKE Autopilot:** Migrated from local Minikube due to memory constraints. Autopilot auto-provisions nodes based on pod resource requests — no manual node pool management.

## Verification

```
$ kubectl get pods
NAME                         READY   STATUS    RESTARTS      AGE
collector-6d496bd89c-rr85d   1/1     Running   1 (74s ago)   5m7s
gateway-6d54764455-fnwkf     1/1     Running   0             5m9s
gateway-6d54764455-zpc4f     1/1     Running   0             5m9s
inference-6d9f444fdb-8h8k9   1/1     Running   2 (43s ago)   3m42s
inference-6d9f444fdb-8mc6n   1/1     Running   0             5m8s
inference-6d9f444fdb-lhzg6   1/1     Running   2 (43s ago)   5m8s
kafka-controller-0           1/1     Running   0             31m
postgresql-0                 1/1     Running   0             114m

$ kubectl exec -i postgresql-0 -- env PGPASSWORD=postgres psql -U postgres -d inference_platform \
    -c "SELECT service_name, timestamp, status, latency_p95_ms, error_rate FROM health_checks ORDER BY timestamp DESC LIMIT 5;"
 service_name |           timestamp           | status  | latency_p95_ms | error_rate
--------------+-------------------------------+---------+----------------+------------
 inference    | 2026-05-26 01:24:51.23186+00  | healthy |                |          0
 gateway      | 2026-05-26 01:24:51.231242+00 | healthy |             10 |          0
 inference    | 2026-05-26 01:24:41.198488+00 | healthy |                |          0
 gateway      | 2026-05-26 01:24:41.197847+00 | healthy |             10 |          0
 inference    | 2026-05-26 01:24:31.165784+00 | healthy |                |          0
```

## Next: Layer 3 — Redis + Dashboard API
- Add Redis for live operational state
- Collector writes current status to Redis after each scrape
- Gateway serves dashboard API: `/api/services/status` (Redis), `/api/services/:name/history` (PostgreSQL)
