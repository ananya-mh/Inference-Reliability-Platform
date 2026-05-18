import { Request, Response, NextFunction } from "express";

const HISTOGRAM_BUCKETS = [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10];

interface HistogramData {
  buckets: Map<number, number>;
  count: number;
  sum: number;
}

const requestCounts = new Map<string, number>();
const requestDurations = new Map<string, HistogramData>();

function getOrCreateHistogram(endpoint: string): HistogramData {
  let histogram = requestDurations.get(endpoint);
  if (!histogram) {
    const buckets = new Map<number, number>();
    for (const bound of HISTOGRAM_BUCKETS) {
      buckets.set(bound, 0);
    }
    histogram = { buckets, count: 0, sum: 0 };
    requestDurations.set(endpoint, histogram);
  }
  return histogram;
}

function recordRequest(endpoint: string, durationSeconds: number): void {
  requestCounts.set(endpoint, (requestCounts.get(endpoint) ?? 0) + 1);

  const histogram = getOrCreateHistogram(endpoint);
  histogram.count += 1;
  histogram.sum += durationSeconds;

  for (const bound of HISTOGRAM_BUCKETS) {
    if (durationSeconds <= bound) {
      histogram.buckets.set(bound, (histogram.buckets.get(bound) ?? 0) + 1);
    }
  }
}

export function metricsMiddleware(
  req: Request,
  _res: Response,
  next: NextFunction
): void {
  const start = process.hrtime.bigint();

  _res.on("finish", () => {
    const end = process.hrtime.bigint();
    const durationNs = Number(end - start);
    const durationSeconds = durationNs / 1e9;
    recordRequest(req.path, durationSeconds);
  });

  next();
}

export function formatPrometheusMetrics(): string {
  const lines: string[] = [];

  lines.push("# HELP gateway_requests_total Total number of requests by endpoint");
  lines.push("# TYPE gateway_requests_total counter");
  for (const [endpoint, count] of requestCounts.entries()) {
    lines.push(`gateway_requests_total{endpoint="${endpoint}"} ${count}`);
  }

  lines.push("");
  lines.push("# HELP gateway_request_duration_seconds Request duration histogram");
  lines.push("# TYPE gateway_request_duration_seconds histogram");
  for (const [endpoint, histogram] of requestDurations.entries()) {
    let cumulative = 0;
    for (const bound of HISTOGRAM_BUCKETS) {
      cumulative += histogram.buckets.get(bound) ?? 0;
      lines.push(
        `gateway_request_duration_seconds_bucket{endpoint="${endpoint}",le="${bound}"} ${cumulative}`
      );
    }
    lines.push(
      `gateway_request_duration_seconds_bucket{endpoint="${endpoint}",le="+Inf"} ${histogram.count}`
    );
    lines.push(
      `gateway_request_duration_seconds_count{endpoint="${endpoint}"} ${histogram.count}`
    );
    lines.push(
      `gateway_request_duration_seconds_sum{endpoint="${endpoint}"} ${histogram.sum}`
    );
  }

  return lines.join("\n") + "\n";
}
