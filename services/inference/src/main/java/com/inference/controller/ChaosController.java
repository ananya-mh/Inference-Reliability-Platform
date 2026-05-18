package com.inference.controller;

import com.inference.model.ApiResponse;
import com.inference.service.ChaosService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/chaos")
public class ChaosController {

    private final ChaosService chaosService;

    public ChaosController(ChaosService chaosService) {
        this.chaosService = chaosService;
    }

    @PostMapping("/enable")
    public ResponseEntity<ApiResponse<Map<String, String>>> enable() {
        chaosService.enableChaos();
        return ResponseEntity.ok(ApiResponse.success(Map.of("message", "chaos mode enabled")));
    }

    @PostMapping("/disable")
    public ResponseEntity<ApiResponse<Map<String, String>>> disable() {
        chaosService.disableChaos();
        return ResponseEntity.ok(ApiResponse.success(Map.of("message", "chaos mode disabled")));
    }

    @GetMapping("/latency")
    public ResponseEntity<ApiResponse<Map<String, Object>>> latency(@RequestParam("ms") long ms) {
        chaosService.setLatency(ms);
        return ResponseEntity.ok(ApiResponse.success(Map.of(
                "message", "additional latency set",
                "latency_ms", ms
        )));
    }
}
