# Kafka on Minikube

Single-broker Kafka in KRaft mode (no ZooKeeper) with auto-provisioned topics.

## Install

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install kafka bitnami/kafka -f k8s/kafka/values.yaml
```

## Verify

```bash
kubectl get pods -l app.kubernetes.io/name=kafka
```

All pods should reach `Running` status within ~2 minutes.

## Topics

Created automatically by the provisioning job:

| Topic | Partitions | Description |
|---|---|---|
| `metrics.health` | 3 | Health check metrics from collector |
| `metrics.incidents` | 1 | Incident events from collector |

## Connection from other services

Broker address inside the cluster: `kafka.default.svc.cluster.local:9092`
