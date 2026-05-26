import express, { Request, Response, NextFunction } from "express";
import Redis from "ioredis";
import { Pool } from "pg";
import { metricsMiddleware, formatPrometheusMetrics } from "./metrics";
import { createDashboardRouter } from "./dashboard";

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

function log(entry: Record<string, unknown>): void {
  process.stdout.write(
    JSON.stringify({ ...entry, timestamp: new Date().toISOString() }) + "\n"
  );
}

const app = express();
const PORT = parseInt(process.env["PORT"] ?? "3000", 10);
const REDIS_URL = process.env["REDIS_URL"] ?? "redis://redis:6379";
const DATABASE_URL =
  process.env["DATABASE_URL"] ??
  "postgresql://postgres:postgres@postgresql:5432/inference_platform";

const redisClient = new Redis(REDIS_URL);
redisClient.on("error", (err: Error) => {
  log({ level: "error", message: "Redis connection error", error: err.message });
});

const pgPool = new Pool({ connectionString: DATABASE_URL });
pgPool.on("error", (err: Error) => {
  log({ level: "error", message: "PostgreSQL pool error", error: err.message });
});

app.use(metricsMiddleware);

app.get("/health", (_req: Request, res: Response) => {
  res.json(
    envelope({
      status: "healthy",
      uptime: process.uptime(),
      timestamp: new Date().toISOString(),
    })
  );
});

app.get("/metrics", (_req: Request, res: Response) => {
  res.set("Content-Type", "text/plain; charset=utf-8");
  res.send(formatPrometheusMetrics());
});

app.use("/api", createDashboardRouter(redisClient, pgPool));

app.use((_req: Request, res: Response) => {
  res.status(404).json(errorEnvelope("Not found"));
});

app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
  log({ level: "error", message: err.message, stack: err.stack });
  res.status(500).json(errorEnvelope("Internal server error"));
});

app.listen(PORT, () => {
  log({ level: "info", message: "Gateway service started", port: PORT });
});

process.on("unhandledRejection", (reason: unknown) => {
  const message = reason instanceof Error ? reason.message : String(reason);
  log({ level: "error", message: "Unhandled rejection", reason: message });
});
