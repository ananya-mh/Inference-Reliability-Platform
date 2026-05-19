# Kubernetes Deployment

## Prerequisites
- Minikube installed
- kubectl installed
- Docker images built locally (from Layer 0)

## Deploy

```bash
# Start Minikube
minikube start

# Point shell at Minikube's Docker daemon, then build images
# PowerShell:
minikube docker-env | Invoke-Expression
# Bash:
eval $(minikube docker-env)

# Build images inside Minikube's Docker
docker compose build

# Enable ingress addon
minikube addons enable ingress

# Deploy all manifests
kubectl apply -f k8s/base/

# Watch pods come up
kubectl get pods -w
```

## Verify

```bash
# All pods should be Running with 0 restarts
kubectl get pods

# Check probe status
kubectl describe pod <pod-name>

# Test through ingress
minikube tunnel   # run in a separate terminal on Windows
curl http://localhost/api/health
curl http://localhost/inference/health
```

## Cleanup

```bash
kubectl delete -f k8s/base/
minikube stop
```
