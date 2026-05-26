import asyncio
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.consumer import MetricsConsumer
from app.publisher import MetricsPublisher
from app.scraper import scrape_service

PORT = int(os.environ.get("PORT", "8000"))
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://gateway:3000")
INFERENCE_URL = os.environ.get("INFERENCE_URL", "http://inference:8080")
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@postgresql:5432/inference_platform",
)
SCRAPE_INTERVAL_SECONDS = int(os.environ.get("SCRAPE_INTERVAL_SECONDS", "10"))

_start_time = time.monotonic()


class JSONLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONLogFormatter())
logging.root.handlers = [handler]
logging.root.setLevel(logging.INFO)

logger = logging.getLogger("collector")

app = FastAPI(title="Collector Service", version="0.2.0")

_http_client: httpx.AsyncClient | None = None
_publisher: MetricsPublisher | None = None
_consumer: MetricsConsumer | None = None
_consumer_thread: threading.Thread | None = None
_scraper_task: asyncio.Task | None = None  # type: ignore[type-arg]
_last_scrape_time: str | None = None
_last_scrape_results: list[dict] = []


def envelope(data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {
        "data": data,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _scrape_loop() -> None:
    global _last_scrape_time, _last_scrape_results

    await asyncio.sleep(2)
    logger.info(
        "scrape loop started: gateway=%s inference=%s interval=%ds",
        GATEWAY_URL, INFERENCE_URL, SCRAPE_INTERVAL_SECONDS,
    )

    while True:
        try:
            results = await asyncio.gather(
                scrape_service(_http_client, "gateway", GATEWAY_URL),
                scrape_service(_http_client, "inference", INFERENCE_URL),
            )

            _last_scrape_time = datetime.now(timezone.utc).isoformat()
            _last_scrape_results = list(results)

            if _publisher is not None:
                for result in results:
                    if result is not None:
                        _publisher.publish_health(result)
                _publisher.flush()

        except Exception:
            logger.exception("scrape loop iteration failed")

        await asyncio.sleep(SCRAPE_INTERVAL_SECONDS)


def _run_consumer() -> None:
    global _consumer
    while True:
        try:
            _consumer = MetricsConsumer(KAFKA_BOOTSTRAP_SERVERS, DATABASE_URL)
            _consumer.run()
            break
        except Exception:
            logger.exception("consumer thread crashed, retrying in 5s")
            time.sleep(5)


@app.on_event("startup")
async def on_startup() -> None:
    global _http_client, _publisher, _consumer_thread, _scraper_task

    logger.info("collector running")

    _http_client = httpx.AsyncClient()

    try:
        _publisher = MetricsPublisher(KAFKA_BOOTSTRAP_SERVERS)
        logger.info("kafka publisher initialized: %s", KAFKA_BOOTSTRAP_SERVERS)
    except Exception:
        logger.exception("failed to initialize kafka publisher — scraping will run but not publish")
        _publisher = None

    _consumer_thread = threading.Thread(target=_run_consumer, daemon=True, name="metrics-consumer")
    _consumer_thread.start()
    logger.info("consumer thread started")

    _scraper_task = asyncio.create_task(_scrape_loop())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    global _scraper_task

    logger.info("shutting down collector")

    if _scraper_task is not None:
        _scraper_task.cancel()
        try:
            await _scraper_task
        except asyncio.CancelledError:
            pass

    if _publisher is not None:
        _publisher.flush()

    if _consumer is not None:
        _consumer.close()

    if _http_client is not None:
        await _http_client.aclose()


@app.get("/health")
async def health() -> dict[str, Any]:
    uptime = round(time.monotonic() - _start_time, 2)
    return envelope(data={
        "status": "healthy",
        "uptime": uptime,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scraper": {
            "last_scrape": _last_scrape_time,
            "services_scraped": len(_last_scrape_results),
        },
    })


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=envelope(error="internal server error"),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT)
