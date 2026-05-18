package com.inference.controller;

import com.inference.model.ApiResponse;
import com.inference.service.ChaosService;
import com.inference.service.MetricsService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;

@RestController
public class PredictController {

    private static final String MODEL_NAME = "inference-v1";

    private final ChaosService chaosService;
    private final MetricsService metricsService;

    public PredictController(ChaosService chaosService, MetricsService metricsService) {
        this.chaosService = chaosService;
        this.metricsService = metricsService;
    }

    @PostMapping("/predict")
    public ResponseEntity<ApiResponse<Map<String, Object>>> predict() {
        long start = System.nanoTime();

        try {
            long baseLatency = ThreadLocalRandom.current().nextLong(50, 201);
            long totalLatency = baseLatency + chaosService.getAdditionalLatencyMs();
            Thread.sleep(totalLatency);

            if (chaosService.isChaosEnabled() && ThreadLocalRandom.current().nextBoolean()) {
                metricsService.recordPrediction("error");
                double durationSeconds = (System.nanoTime() - start) / 1_000_000_000.0;
                metricsService.recordRequest("/predict", durationSeconds);
                return ResponseEntity.status(500)
                        .body(ApiResponse.error("inference failed — chaos mode induced error"));
            }

            double[] predictions = new double[]{
                    ThreadLocalRandom.current().nextDouble(),
                    ThreadLocalRandom.current().nextDouble(),
                    ThreadLocalRandom.current().nextDouble()
            };

            double durationSeconds = (System.nanoTime() - start) / 1_000_000_000.0;
            metricsService.recordPrediction("success");
            metricsService.recordRequest("/predict", durationSeconds);

            Map<String, Object> data = Map.of(
                    "model", MODEL_NAME,
                    "predictions", predictions,
                    "latency_ms", totalLatency
            );
            return ResponseEntity.ok(ApiResponse.success(data));

        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            double durationSeconds = (System.nanoTime() - start) / 1_000_000_000.0;
            metricsService.recordPrediction("error");
            metricsService.recordRequest("/predict", durationSeconds);
            return ResponseEntity.status(500)
                    .body(ApiResponse.error("prediction interrupted"));
        }
    }
}
