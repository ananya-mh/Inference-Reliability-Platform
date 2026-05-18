package com.inference.service;

import org.springframework.stereotype.Service;

import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.LongAdder;

@Service
public class MetricsService {

    private static final double[] HISTOGRAM_BUCKETS = {0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0};

    private final ConcurrentHashMap<String, LongAdder> requestCounts = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, LongAdder> predictionCounts = new ConcurrentHashMap<>();
    private final CopyOnWriteArrayList<Double> durations = new CopyOnWriteArrayList<>();

    public void recordRequest(String endpoint, double durationSeconds) {
        requestCounts.computeIfAbsent(endpoint, k -> new LongAdder()).increment();
        durations.add(durationSeconds);
    }

    public void recordPrediction(String status) {
        predictionCounts.computeIfAbsent(status, k -> new LongAdder()).increment();
    }

    public String toPrometheusFormat() {
        StringBuilder sb = new StringBuilder();

        sb.append("# HELP inference_requests_total Total number of requests by endpoint\n");
        sb.append("# TYPE inference_requests_total counter\n");
        for (var entry : requestCounts.entrySet()) {
            sb.append("inference_requests_total{endpoint=\"")
                    .append(entry.getKey())
                    .append("\"} ")
                    .append(entry.getValue().sum())
                    .append("\n");
        }

        sb.append("# HELP inference_predictions_total Total number of predictions by status\n");
        sb.append("# TYPE inference_predictions_total counter\n");
        for (var entry : predictionCounts.entrySet()) {
            sb.append("inference_predictions_total{status=\"")
                    .append(entry.getKey())
                    .append("\"} ")
                    .append(entry.getValue().sum())
                    .append("\n");
        }

        List<Double> snapshot = List.copyOf(durations);
        long count = snapshot.size();
        double sum = snapshot.stream().mapToDouble(Double::doubleValue).sum();

        sb.append("# HELP inference_request_duration_seconds Request duration histogram\n");
        sb.append("# TYPE inference_request_duration_seconds histogram\n");
        for (double bucket : HISTOGRAM_BUCKETS) {
            long bucketCount = snapshot.stream().filter(d -> d <= bucket).count();
            sb.append("inference_request_duration_seconds_bucket{le=\"")
                    .append(formatBucket(bucket))
                    .append("\"} ")
                    .append(bucketCount)
                    .append("\n");
        }
        sb.append("inference_request_duration_seconds_bucket{le=\"+Inf\"} ").append(count).append("\n");
        sb.append("inference_request_duration_seconds_count ").append(count).append("\n");
        sb.append("inference_request_duration_seconds_sum ").append(String.format("%.6f", sum)).append("\n");

        return sb.toString();
    }

    private String formatBucket(double value) {
        if (value == (long) value) {
            return String.valueOf((long) value);
        }
        return String.valueOf(value);
    }
}
