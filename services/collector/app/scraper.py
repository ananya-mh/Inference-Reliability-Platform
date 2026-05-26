import logging
import re
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("collector.scraper")

HISTOGRAM_BUCKETS = [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

ERROR_RATE_DEGRADED_THRESHOLD = 0.05
P95_DEGRADED_THRESHOLD_MS = 500.0


def parse_prometheus_text(text: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r'^([a-zA-Z_:][a-zA-Z0-9_:]*(?:\{[^}]*\})?)\s+([0-9eE.+\-]+)$', line)
        if match:
            key = match.group(1)
            try:
                metrics[key] = float(match.group(2))
            except ValueError:
                continue
    return metrics


def _compute_p95_from_histogram(metrics: dict[str, float], prefix: str) -> float | None:
    total_count = 0.0
    for key, value in metrics.items():
        if key.startswith(f"{prefix}_bucket") and '+Inf' in key:
            total_count += value

    if total_count == 0:
        return None

    threshold = 0.95 * total_count
    cumulative_by_bucket: dict[float, float] = {}

    for key, value in metrics.items():
        if not key.startswith(f"{prefix}_bucket"):
            continue
        le_match = re.search(r'le="([^"]+)"', key)
        if not le_match:
            continue
        le_str = le_match.group(1)
        if le_str == "+Inf":
            continue
        try:
            le_val = float(le_str)
        except ValueError:
            continue

        endpoint_match = re.search(r'endpoint="([^"]*)"', key)
        bucket_key = le_val
        if endpoint_match:
            cumulative_by_bucket[bucket_key] = cumulative_by_bucket.get(bucket_key, 0) + value
        else:
            cumulative_by_bucket[bucket_key] = cumulative_by_bucket.get(bucket_key, 0) + value

    for bucket in sorted(cumulative_by_bucket.keys()):
        if cumulative_by_bucket[bucket] >= threshold:
            return bucket * 1000.0

    sum_val = 0.0
    count_val = 0.0
    for key, value in metrics.items():
        if key.startswith(f"{prefix}_sum"):
            sum_val += value
        elif key.startswith(f"{prefix}_count"):
            count_val += value
    if count_val > 0:
        return (sum_val / count_val) * 1000.0
    return None


def _compute_error_rate(metrics: dict[str, float], service_name: str) -> float:
    if service_name == "inference":
        error_count = 0.0
        success_count = 0.0
        for key, value in metrics.items():
            if "predictions_total" in key and 'status="error"' in key:
                error_count += value
            elif "predictions_total" in key and 'status="success"' in key:
                success_count += value
        total = error_count + success_count
        if total == 0:
            return 0.0
        return error_count / total

    total_requests = 0.0
    for key, value in metrics.items():
        if "_requests_total" in key:
            total_requests += value
    if total_requests == 0:
        return 0.0
    return 0.0


def _determine_status(error_rate: float, p95_ms: float | None) -> str:
    if p95_ms is not None and p95_ms > P95_DEGRADED_THRESHOLD_MS:
        return "degraded"
    if error_rate > ERROR_RATE_DEGRADED_THRESHOLD:
        return "degraded"
    return "healthy"


async def scrape_service(
    client: httpx.AsyncClient, name: str, url: str
) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        response = await client.get(f"{url}/metrics", timeout=5.0)
        response.raise_for_status()
        raw_text = response.text
    except Exception as exc:
        logger.warning("scrape failed for %s at %s: %s", name, url, exc)
        return {
            "service_name": name,
            "status": "down",
            "latency_p95_ms": None,
            "error_rate": None,
            "raw_metrics": None,
            "timestamp": timestamp,
        }

    metrics = parse_prometheus_text(raw_text)

    prefix = f"{name}_request_duration_seconds"
    p95_ms = _compute_p95_from_histogram(metrics, prefix)
    error_rate = _compute_error_rate(metrics, name)
    status = _determine_status(error_rate, p95_ms)

    logger.info(
        "scraped %s: status=%s p95=%.2fms error_rate=%.4f",
        name, status, p95_ms or 0.0, error_rate,
    )

    return {
        "service_name": name,
        "status": status,
        "latency_p95_ms": p95_ms,
        "error_rate": error_rate,
        "raw_metrics": metrics,
        "timestamp": timestamp,
    }
