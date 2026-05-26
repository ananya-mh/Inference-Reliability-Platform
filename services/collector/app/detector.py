import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("collector.detector")

ERROR_RATE_THRESHOLD = 0.05
LATENCY_P95_THRESHOLD = 500.0
SUSTAINED_CHECKS = 2


class IncidentDetector:
    def __init__(self) -> None:
        self._breach_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._active_incidents: dict[str, dict[str, dict[str, Any]]] = {}

    def check(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        incidents: list[dict[str, Any]] = []

        for result in results:
            if result is None:
                continue
            name = result["service_name"]
            now = datetime.now(timezone.utc).isoformat()

            status = result.get("status", "healthy")
            error_rate = result.get("error_rate") or 0.0
            latency = result.get("latency_p95_ms") or 0.0

            is_down = status == "down"

            if is_down or error_rate > ERROR_RATE_THRESHOLD:
                self._breach_counts[name]["high_error_rate"] += 1
            else:
                self._breach_counts[name]["high_error_rate"] = 0
                resolved = self._resolve_if_active(name, "high_error_rate", now)
                if resolved:
                    incidents.append(resolved)

            if latency > LATENCY_P95_THRESHOLD:
                self._breach_counts[name]["high_latency"] += 1
            else:
                self._breach_counts[name]["high_latency"] = 0
                resolved = self._resolve_if_active(name, "high_latency", now)
                if resolved:
                    incidents.append(resolved)

            if self._breach_counts[name]["high_error_rate"] >= SUSTAINED_CHECKS:
                details: dict[str, Any] = {"status": status}
                if is_down:
                    details["reason"] = "service unreachable"
                else:
                    details["error_rate"] = error_rate
                incident = self._create_if_new(name, "high_error_rate", now, details)
                if incident:
                    incidents.append(incident)

            if self._breach_counts[name]["high_latency"] >= SUSTAINED_CHECKS:
                incident = self._create_if_new(name, "high_latency", now, {
                    "latency_p95_ms": latency,
                })
                if incident:
                    incidents.append(incident)

        return incidents

    def _create_if_new(
        self, service: str, incident_type: str, now: str, details: dict[str, Any]
    ) -> dict[str, Any] | None:
        key = f"{service}:{incident_type}"
        if key in self._active_incidents:
            return None

        incident: dict[str, Any] = {
            "type": incident_type,
            "root_cause_service": service,
            "affected_services": [service],
            "started_at": now,
            "resolved_at": None,
            "details": details,
        }
        self._active_incidents[key] = incident
        logger.info(
            "incident created: type=%s service=%s details=%s",
            incident_type, service, json.dumps(details),
        )
        return incident

    def _resolve_if_active(
        self, service: str, incident_type: str, now: str
    ) -> dict[str, Any] | None:
        key = f"{service}:{incident_type}"
        if key not in self._active_incidents:
            return None

        incident = self._active_incidents.pop(key)
        resolved = {**incident, "resolved_at": now}
        logger.info(
            "incident resolved: type=%s service=%s",
            incident_type, service,
        )
        return resolved

    @property
    def has_active(self) -> bool:
        return len(self._active_incidents) > 0
