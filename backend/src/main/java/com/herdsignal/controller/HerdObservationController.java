package com.herdsignal.controller;

import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.HerdObservationHistoryResponse;
import com.herdsignal.dto.HerdObservationResponse;
import com.herdsignal.service.HerdObservationService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/** v4와 분리된 State S1 관찰 전용 API. */
@RestController
@RequestMapping("/api/observations")
@RequiredArgsConstructor
public class HerdObservationController {
    private final HerdObservationService service;

    @GetMapping("/{ticker}")
    public ResponseEntity<ApiResponse<HerdObservationResponse>> getLatest(
            @PathVariable String ticker
    ) {
        return ResponseEntity.ok(ApiResponse.success(service.getLatest(ticker)));
    }

    @GetMapping("/{ticker}/history")
    public ResponseEntity<ApiResponse<HerdObservationHistoryResponse>> getHistory(
            @PathVariable String ticker,
            @RequestParam(required = false) Integer limit
    ) {
        return ResponseEntity.ok(
                ApiResponse.success(service.getHistory(ticker, limit))
        );
    }
}
