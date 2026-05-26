import { Router, Request, Response } from "express";
import Redis from "ioredis";
import { Pool } from "pg";

interface ServiceStatus {
  name: string;
  status: string;
  latency_p95_ms: number;
  error_rate: number;
  last_check: string | null;
}

interface HealthCheckRow {
  id: number;
  service_name: string;
  timestamp: string;
  status: string;
  latency_p95_ms: number | null;
  error_rate: number | null;
  raw_metrics: Record<string, unknown> | null;
}

interface IncidentRow {
  id: number;
  type: string;
  root_cause_service: string | null;
  affected_services: string[] | null;
  started_at: string;
  resolved_at: string | null;
  details: Record<string, unknown> | null;
}

interface ApiEnvelope<T> {
  data: T | null;
  error: string | null;
  timestamp: string;
}

function envelope<T>(data: T): ApiEnvelope<T> {
  return { data, error: null, timestamp: new Date().toISOString() };
}

function errorEnvelope(message: string): ApiEnvelope<null> {
  return { data: null, error: message, timestamp: new Date().toISOString() };
}

const RANGE_TO_INTERVAL: Record<string, string> = {
  "1h": "1 hour",
  "6h": "6 hours",
  "24h": "24 hours",
  "7d": "7 days",
};

export function createDashboardRouter(
  redisClient: Redis,
  pgPool: Pool
): Router {
  const router = Router();

  router.get("/services/status", async (_req: Request, res: Response) => {
    try {
      const keys = await redisClient.keys("service:*:status");
      const services: ServiceStatus[] = [];

      for (const key of keys) {
        const name = key.split(":")[1];
        const [status, p95, errorRate, lastCheck] = await Promise.all([
          redisClient.get(`service:${name}:status`),
          redisClient.get(`service:${name}:p95`),
          redisClient.get(`service:${name}:error_rate`),
          redisClient.get(`service:${name}:last_check`),
        ]);

        services.push({
          name,
          status: status ?? "unknown",
          latency_p95_ms: parseFloat(p95 ?? "0"),
          error_rate: parseFloat(errorRate ?? "0"),
          last_check: lastCheck,
        });
      }

      res.json(envelope(services));
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      res.status(500).json(errorEnvelope(message));
    }
  });

  router.get(
    "/services/:name/history",
    async (req: Request, res: Response) => {
      try {
        const { name } = req.params;
        const range = (req.query["range"] as string) ?? "1h";
        const interval = RANGE_TO_INTERVAL[range];

        if (!interval) {
          res
            .status(400)
            .json(errorEnvelope("Invalid range. Use: 1h, 6h, 24h, 7d"));
          return;
        }

        const result = await pgPool.query<HealthCheckRow>(
          `SELECT id, service_name, timestamp, status, latency_p95_ms, error_rate, raw_metrics
           FROM health_checks
           WHERE service_name = $1 AND timestamp > NOW() - $2::interval
           ORDER BY timestamp DESC`,
          [name, interval]
        );

        res.json(envelope(result.rows));
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        res.status(500).json(errorEnvelope(message));
      }
    }
  );

  router.get("/incidents", async (_req: Request, res: Response) => {
    try {
      const result = await pgPool.query<IncidentRow>(
        `SELECT id, type, root_cause_service, affected_services, started_at, resolved_at, details
         FROM incidents
         ORDER BY started_at DESC
         LIMIT 50`
      );

      res.json(envelope(result.rows));
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      res.status(500).json(errorEnvelope(message));
    }
  });

  router.get("/incidents/active", async (_req: Request, res: Response) => {
    try {
      const result = await pgPool.query<IncidentRow>(
        `SELECT id, type, root_cause_service, affected_services, started_at, resolved_at, details
         FROM incidents
         WHERE resolved_at IS NULL
         ORDER BY started_at DESC`
      );

      res.json(envelope(result.rows));
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      res.status(500).json(errorEnvelope(message));
    }
  });

  return router;
}
