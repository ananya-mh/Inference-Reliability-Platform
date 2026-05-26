import json
import logging
from typing import Any

from confluent_kafka import Producer

logger = logging.getLogger("collector.publisher")


def _delivery_callback(err: Any, msg: Any) -> None:
    if err is not None:
        logger.error("kafka delivery failed: %s", err)
    else:
        logger.debug("delivered to %s [%d] @ %d", msg.topic(), msg.partition(), msg.offset())


class MetricsPublisher:
    def __init__(self, bootstrap_servers: str) -> None:
        self._producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "client.id": "collector-producer",
            "acks": "all",
        })

    def publish_health(self, metrics: dict) -> None:
        payload = json.dumps(metrics, default=str).encode("utf-8")
        self._producer.produce(
            topic="metrics.health",
            value=payload,
            key=metrics.get("service_name", "unknown").encode("utf-8"),
            callback=_delivery_callback,
        )
        self._producer.poll(0)

    def publish_incident(self, incident: dict) -> None:
        payload = json.dumps(incident, default=str).encode("utf-8")
        self._producer.produce(
            topic="metrics.incidents",
            value=payload,
            key=incident.get("type", "unknown").encode("utf-8"),
            callback=_delivery_callback,
        )
        self._producer.poll(0)

    def flush(self) -> None:
        self._producer.flush(timeout=5.0)
