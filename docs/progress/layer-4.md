# Layer 4 — Incident Detection + Chaos

**Status:** Complete  
**Date:** 2026-05-25

## What I did

1. Created `services/collector/app/detector.py` — an IncidentDetector class that tracks per-service metrics history and checks threshold rules after each scrape cycle:
   - `error_rate > 0.05` sustained for 2+ checks → `high_error_rate` incident
   - `latency_p95_ms > 500` sustained for 2+ checks → `high_latency` incident
   - `status == "down"` (service unreachable) sustained for 2+ checks → `high_error_rate` incident with "service unreachable" reason
   - Auto-resolves incidents when metrics return to normal
2. Updated the consumer (`consumer.py`) to subscribe to both `metrics.health` and `metrics.incidents` topics. Incident messages are either INSERTed (new) or UPDATEd (resolved) in PostgreSQL.
3. Integrated the detector into the main scrape loop (`main.py`). After each scrape cycle: publish incidents to Kafka, update Redis incident state keys (`incident:active`, `incident:latest`).
4. Verified all chaos endpoints on inference service: `/chaos/enable` (50% errors on `/predict`, 503 on `/ready`), `/chaos/disable`, `/chaos/latency?ms=N`.
5. Discovered that chaos mode causes Kubernetes to remove all inference pods from the Service (readiness probe fails → no endpoints). This means the collector can't even reach `/metrics`, so the scraper reports "down" status. Updated the detector to treat "down" as a threshold breach.
6. Wrote `scripts/demo-chaos.sh` — runs chaos → waits → checks incidents → disables chaos → verifies resolution, all via `kubectl exec`.

## What was built

Automated incident detection with full create-resolve lifecycle.

| Resource | File | Details |
|----------|------|---------|
| Incident detector | `services/collector/app/detector.py` | Threshold checks, sustained breach tracking, auto-resolve |
| Updated consumer | `services/collector/app/consumer.py` | Subscribes to metrics.incidents, upserts incidents in PostgreSQL |
| Updated main | `services/collector/app/main.py` | Integrates detector, publishes incidents, updates Redis |
| Demo script | `scripts/demo-chaos.sh` | End-to-end chaos → incident → recovery demo |

## Design choices

**Sustained checks, not single spikes:** Requiring 2+ consecutive threshold breaches (20 seconds at 10s scrape interval) prevents false positives from transient blips. A single bad scrape doesn't create an incident.

**"Down" status as high_error_rate:** When Kubernetes removes all inference pods from the Service (because readiness probes fail), the scraper can't connect at all. Rather than adding a separate "service_down" incident type, this is treated as the most extreme form of high_error_rate. The `details` field records `{"status": "down", "reason": "service unreachable"}` to distinguish it from actual error rate breaches.

**In-memory state, not persistent:** The detector tracks breach counts and active incidents in memory. If the collector restarts during an incident, it loses that state. This is acceptable for dev — in production you'd persist to Redis. The trade-off is simplicity: no coordination between scrape loop and external state store.

**Upsert pattern for incidents:** The consumer uses INSERT for new incidents and UPDATE (matching on type + root_cause_service where resolved_at IS NULL) for resolutions. This avoids duplicate incidents if the same message is consumed twice.

## Verification

```
# Enable chaos on all inference pods
$ for pod in $(kubectl get pods -l app=inference -o jsonpath='{.items[*].metadata.name}'); do
    kubectl exec "$pod" -- wget -qO- --post-data="" http://localhost:8080/chaos/enable
  done

# ~20s later, incident detected:
collector.detector: incident created: type=high_error_rate service=inference details={"status": "down", "reason": "service unreachable"}
collector.consumer: inserted incident: type=high_error_rate service=inference

# Verify via API:
$ curl http://localhost:3000/api/incidents
→ { "data": [{ "type": "high_error_rate", "root_cause_service": "inference", "resolved_at": null }] }

# Disable chaos:
$ for pod in ...; do kubectl exec "$pod" -- wget -qO- --post-data="" http://localhost:8080/chaos/disable; done

# ~10s later:
collector.detector: incident resolved: type=high_error_rate service=inference

# Verify resolved:
$ psql: SELECT started_at, resolved_at FROM incidents;
→ started_at: 2026-05-26 03:17:26, resolved_at: 2026-05-26 03:18:37
```

## Next: Layer 5 — Cascading Failure Detection + LLM Root-Cause + HPA
- Dependency graph for cascading failure correlation
- LLM-powered root-cause summaries
- Horizontal Pod Autoscaler for gateway and inference
