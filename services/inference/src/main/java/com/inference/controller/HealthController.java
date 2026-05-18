package com.inference.controller;

import com.inference.model.ApiResponse;
import com.inference.service.ChaosService;
import com.inference.service.MetricsService;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.lang.management.ManagementFactory;
import java.util.Map;

@RestController
public class HealthController {

    private final MetricsService metricsService;
    private final ChaosService chaosService;

    public HealthController(MetricsService metricsService, ChaosService chaosService) {
        this.metricsService = metricsService;
        this.chaosService = chaosService;
    }

    @GetMapping("/health")
    public ResponseEntity<ApiResponse<Map<String, Object>>> health() {
        Map<String, Object> data = Map.of(
                "status", "healthy",
                "uptime", ManagementFactory.getRuntimeMXBean().getUptime(),
                "timestamp", java.time.Instant.now().toString()
        );
        return ResponseEntity.ok(ApiResponse.success(data));
    }

    @GetMapping(value = "/metrics", produces = MediaType.TEXT_PLAIN_VALUE)
    public ResponseEntity<String> metrics() {
        return ResponseEntity.ok(metricsService.toPrometheusFormat());
    }

    @GetMapping("/ready")
    public ResponseEntity<ApiResponse<Map<String, String>>> ready() {
        if (chaosService.isChaosEnabled()) {
            return ResponseEntity.status(503)
                    .body(ApiResponse.error("service degraded — chaos mode active"));
        }
        return ResponseEntity.ok(ApiResponse.success(Map.of("status", "ready")));
    }
}
