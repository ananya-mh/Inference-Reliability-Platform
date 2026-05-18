package com.inference.service;

import org.springframework.stereotype.Service;

@Service
public class ChaosService {

    private volatile boolean chaosEnabled = false;
    private volatile long additionalLatencyMs = 0;

    public void enableChaos() {
        this.chaosEnabled = true;
    }

    public void disableChaos() {
        this.chaosEnabled = false;
        this.additionalLatencyMs = 0;
    }

    public void setLatency(long ms) {
        this.additionalLatencyMs = ms;
    }

    public boolean isChaosEnabled() {
        return chaosEnabled;
    }

    public long getAdditionalLatencyMs() {
        return additionalLatencyMs;
    }
}
