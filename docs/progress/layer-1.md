# Layer 1 — Kubernetes Deployment

**Status:** Complete  
**Date:** 2026-05-19

## What I did

1. Wrote k8s manifests for all three services (Deployment + Service each) and an Ingress resource — placed in `k8s/base/`.
2. Started Minikube with Docker driver (`--memory=4096 --cpus=2`). Hit `icacls.exe` PATH issue on Windows — fixed by ensuring `C:\Windows\System32` is in PATH before running Minikube.
3. Docker Desktop had corrupted containerd blobs from a previous crash (Layer 0's distroless image attempt). Required a full "Purge data" from Docker Desktop settings before anything would work.
4. Pointed shell at Minikube's Docker daemon (`minikube docker-env | Invoke-Expression`) and rebuilt all three images inside Minikube — images came out smaller than local builds (gateway 202MB, inference 228MB, collector 179MB) due to Minikube's Docker using different storage driver.
5. Fixed image names in manifests — `docker compose build` prefixes images with project name (`inference-reliability-platform-gateway` not `gateway`), so manifests needed the full names.
6. Enabled ingress addon, applied all manifests, verified 6 pods Running with 0 restarts.
7. Started `minikube tunnel` for localhost access on Windows, tested all endpoints through Ingress.

## What was built

Kubernetes manifests deploying all three services to Minikube with health probes and Ingress routing.

| Resource | File | Details |
|----------|------|---------|
| gateway Deployment + Service | `k8s/base/gateway.yaml` | 2 replicas, port 3000 |
| inference Deployment + Service | `k8s/base/inference.yaml` | 3 replicas, port 8080 |
| collector Deployment + Service | `k8s/base/collector.yaml` | 1 replica, port 8000 |
| Ingress | `k8s/base/ingress.yaml` | `/api/*` → gateway, `/inference/*` → inference |
| README | `k8s/README.md` | Deploy/verify/cleanup commands |

## Design choices

**Readiness vs liveness probes on inference:** Readiness uses `/ready` (returns 503 during chaos mode), liveness uses `/health` (always 200). This means during chaos injection, k8s stops routing traffic to inference pods (readiness fails) but doesn't kill them (liveness passes). When chaos is disabled, pods become ready again without a restart cycle.

**Gateway and collector probes:** Both use `/health` for readiness and liveness — they don't have a degraded state that needs separate handling yet.

**Resource limits:** Inference gets more memory (256Mi request, 512Mi limit) because the JVM needs headroom. Gateway and collector are lighter (128Mi/256Mi).

**Ingress rewrite-target:** The annotation `nginx.ingress.kubernetes.io/rewrite-target: /$2` with regex paths like `/api(/|$)(.*)` strips the prefix. So `/api/health` hits gateway as `/health`, `/inference/predict` hits inference as `/predict`.

**imagePullPolicy: Never:** Since we build images directly in Minikube's Docker daemon, there's no registry to pull from.

## Verification

```
$ kubectl get pods
NAME                         READY   STATUS    RESTARTS   AGE
collector-695f6778d7-6cqs9   1/1     Running   0          4m43s
gateway-57d8fcb898-bhjvt     1/1     Running   0          4m43s
gateway-57d8fcb898-zwnqg     1/1     Running   0          4m43s
inference-5d8d64869-f9f94    1/1     Running   0          4m43s
inference-5d8d64869-gg26s    1/1     Running   0          4m43s
inference-5d8d64869-xfcdd    1/1     Running   0          4m43s

$ curl http://127.0.0.1/api/health       → 200 { status: "healthy" }
$ curl http://127.0.0.1/inference/health  → 200 { status: "healthy" }
$ curl -X POST http://127.0.0.1/inference/predict → 200 { model: "inference-v1", latency_ms: 185 }
```

## Next: Layer 2 — Kafka + metrics streaming
- Kafka (Helm chart) + PostgreSQL for persistent storage
- Collector scrapes /metrics from gateway and inference every 10s
- Metrics published to Kafka, consumed and written to PostgreSQL
