# Install PostgreSQL
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install postgresql bitnami/postgresql -f k8s/postgresql/values.yaml
# Verify
kubectl get pods -l app.kubernetes.io/name=postgresql
# Apply schema
kubectl exec -it postgresql-0 -- psql -U postgres -d inference_platform -f /tmp/schema.sql
# Or copy schema first:
kubectl cp k8s/postgresql/schema.sql postgresql-0:/tmp/schema.sql
kubectl exec -it postgresql-0 -- psql -U postgres -d inference_platform -f /tmp/schema.sql
