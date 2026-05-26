CREATE TABLE health_checks (
  id SERIAL PRIMARY KEY,
  service_name VARCHAR(50) NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL,
  status VARCHAR(20) NOT NULL,
  latency_p95_ms FLOAT,
  error_rate FLOAT,
  raw_metrics JSONB
);

CREATE TABLE incidents (
  id SERIAL PRIMARY KEY,
  type VARCHAR(50) NOT NULL,
  root_cause_service VARCHAR(50),
  affected_services TEXT[],
  started_at TIMESTAMPTZ NOT NULL,
  resolved_at TIMESTAMPTZ,
  details JSONB
);

CREATE INDEX idx_health_service_time ON health_checks(service_name, timestamp DESC);
CREATE INDEX idx_incidents_active ON incidents(resolved_at) WHERE resolved_at IS NULL;
