package com.inference.model;

import java.time.Instant;

public record ApiResponse<T>(T data, String error, String timestamp) {

    public static <T> ApiResponse<T> success(T data) {
        return new ApiResponse<>(data, null, Instant.now().toString());
    }

    public static <T> ApiResponse<T> error(String error) {
        return new ApiResponse<>(null, error, Instant.now().toString());
    }
}
