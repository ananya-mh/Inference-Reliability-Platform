# Kubernetes Deployment

## Prerequisites
- GKE Autopilot cluster running
- kubectl connected (`gcloud container clusters get-credentials inference-cluster --region us-south1`)
- Images pushed to Artifact Registry
- Helm installed (for PostgreSQL)

## Deploy

```bash
# 1. Infrastructure
helm install postgresql bitnami/postgresql -f k8s/postgresql/values.yaml
kubectl apply -f k8s/kafka/kafka.yaml
kubectl apply -f k8s/redis/redis.yaml

# 2. Wait for infra pods
kubectl get pods -w   # wait until kafka-controller-0, postgresql-0, redis-0 are Running

# 3. Apply database schema
kubectl exec -i postgresql-0 -- env PGPASSWORD=postgres \
  psql -U postgres -d inference_platform < k8s/postgresql/schema.sql

# 4. Deploy application
kubectl apply -f k8s/base/

# 5. Watch all pods come up
kubectl get pods -w
```

## Verify

```bash
# All pods Running
kubectl get pods

# Port-forward and test
kubectl port-forward svc/gateway 3000:3000
curl http://localhost:3000/health
curl http://localhost:3000/api/services/status
curl http://localhost:3000/api/incidents/active

# Check health_checks populating
kubectl exec -i postgresql-0 -- env PGPASSWORD=postgres \
  psql -U postgres -d inference_platform \
  -c "SELECT service_name, status, timestamp FROM health_checks ORDER BY timestamp DESC LIMIT 5;"
```

## Cleanup

```bash
kubectl delete -f k8s/base/
kubectl delete -f k8s/kafka/kafka.yaml
kubectl delete -f k8s/redis/redis.yaml
helm uninstall postgresql
kubectl delete pvc --all
```
