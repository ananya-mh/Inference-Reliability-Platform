import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

PORT = int(os.environ.get("PORT", "8000"))

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

app = FastAPI(title="Collector Service", version="0.1.0")


def envelope(data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {
        "data": data,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("collector running")


@app.get("/health")
async def health() -> dict[str, Any]:
    uptime = round(time.monotonic() - _start_time, 2)
    return envelope(data={
        "status": "healthy",
        "uptime": uptime,
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
