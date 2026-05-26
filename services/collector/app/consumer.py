import json
import logging
from typing import Any

import psycopg2
from confluent_kafka import Consumer, KafkaError

logger = logging.getLogger("collector.consumer")


class MetricsConsumer:
    def __init__(self, bootstrap_servers: str, db_dsn: str) -> None:
        self._db_dsn = db_dsn
        self._consumer = Consumer({
            "bootstrap.servers": bootstrap_servers,
            "group.id": "collector-consumer",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        })
        self._conn = psycopg2.connect(db_dsn)
        self._conn.autocommit = True
        self._running = True

    def _reconnect_db(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
        self._conn = psycopg2.connect(self._db_dsn)
        self._conn.autocommit = True
        logger.info("reconnected to database")

    def run(self) -> None:
        self._consumer.subscribe(["metrics.health"])
        logger.info("consumer started, subscribed to metrics.health")

        while self._running:
            msg = self._consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("consumer error: %s", msg.error())
                continue

            try:
                data = json.loads(msg.value().decode("utf-8"))
                self._insert_health_check(data)
            except psycopg2.OperationalError:
                logger.exception("database connection lost, reconnecting")
                try:
                    self._reconnect_db()
                except Exception:
                    logger.exception("reconnect failed, will retry next message")
            except Exception:
                logger.exception("failed to process message")

    def _insert_health_check(self, data: dict[str, Any]) -> None:
        raw_metrics = data.get("raw_metrics")
        raw_json = json.dumps(raw_metrics) if raw_metrics is not None else None

        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO health_checks
                    (service_name, timestamp, status, latency_p95_ms, error_rate, raw_metrics)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    data["service_name"],
                    data["timestamp"],
                    data["status"],
                    data.get("latency_p95_ms"),
                    data.get("error_rate"),
                    raw_json,
                ),
            )

    def close(self) -> None:
        self._running = False
        try:
            self._consumer.close()
        except Exception:
            logger.exception("error closing consumer")
        try:
            self._conn.close()
        except Exception:
            logger.exception("error closing db connection")
