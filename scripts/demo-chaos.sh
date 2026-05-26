#!/usr/bin/env bash
set -euo pipefail

INFERENCE_POD=$(kubectl get pod -l app=inference -o jsonpath='{.items[0].metadata.name}')
GATEWAY_POD=$(kubectl get pod -l app=gateway -o jsonpath='{.items[0].metadata.name}')

echo "=== Chaos Demo ==="
echo ""

echo "1. Checking current service status..."
kubectl exec "$GATEWAY_POD" -- wget -qO- http://localhost:3000/api/services/status 2>/dev/null || \
  kubectl exec "$GATEWAY_POD" -- curl -s http://localhost:3000/api/services/status
echo ""

echo "2. Enabling chaos on inference service..."
kubectl exec "$INFERENCE_POD" -- wget -qO- --post-data="" http://localhost:8080/chaos/enable 2>/dev/null || \
  kubectl exec "$INFERENCE_POD" -- curl -s -X POST http://localhost:8080/chaos/enable
echo ""

echo "3. Waiting 30s for incident detection..."
for i in $(seq 30 -5 5); do
  echo "   ${i}s remaining..."
  sleep 5
done
echo ""

echo "4. Checking active incidents..."
kubectl exec "$GATEWAY_POD" -- wget -qO- http://localhost:3000/api/incidents/active 2>/dev/null || \
  kubectl exec "$GATEWAY_POD" -- curl -s http://localhost:3000/api/incidents/active
echo ""

echo "5. Checking service status (should show degraded)..."
kubectl exec "$GATEWAY_POD" -- wget -qO- http://localhost:3000/api/services/status 2>/dev/null || \
  kubectl exec "$GATEWAY_POD" -- curl -s http://localhost:3000/api/services/status
echo ""

echo "6. Disabling chaos on inference service..."
kubectl exec "$INFERENCE_POD" -- wget -qO- --post-data="" http://localhost:8080/chaos/disable 2>/dev/null || \
  kubectl exec "$INFERENCE_POD" -- curl -s -X POST http://localhost:8080/chaos/disable
echo ""

echo "7. Waiting 30s for recovery..."
for i in $(seq 30 -5 5); do
  echo "   ${i}s remaining..."
  sleep 5
done
echo ""

echo "8. Checking incidents (should show resolved)..."
kubectl exec "$GATEWAY_POD" -- wget -qO- http://localhost:3000/api/incidents 2>/dev/null || \
  kubectl exec "$GATEWAY_POD" -- curl -s http://localhost:3000/api/incidents
echo ""

echo "=== Demo complete ==="
