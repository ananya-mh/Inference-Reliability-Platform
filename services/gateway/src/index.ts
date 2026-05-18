import express, { Request, Response, NextFunction } from "express";
import { metricsMiddleware, formatPrometheusMetrics } from "./metrics";

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
