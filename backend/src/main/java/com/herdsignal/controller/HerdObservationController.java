package com.herdsignal.controller;

import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.HerdObservationBatchResponse;
import com.herdsignal.dto.HerdObservationHistoryResponse;
import com.herdsignal.dto.HerdObservationResponse;
import com.herdsignal.dto.HerdPriceTimelineResponse;
import com.herdsignal.service.HerdObservationService;
import com.herdsignal.service.HerdPriceTimelineService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Arrays;

/** v4와 분리된 State S1 관찰 전용 API. */
@RestController
@RequestMapping("/api/observations")
@RequiredArgsConstructor
public class HerdObservationController {
    private final HerdObservationService service;
    private final HerdPriceTimelineService timelineService;

    @GetMapping
    public ResponseEntity<ApiResponse<HerdObservationBatchResponse>> getLatestBatch(
            @RequestParam String tickers
    ) {
        return ResponseEntity.ok(ApiResponse.success(
                service.getLatestBatch(Arrays.asList(tickers.split(",")))
        ));
    }

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

    @GetMapping("/{ticker}/timeline")
    public ResponseEntity<ApiResponse<HerdPriceTimelineResponse>> getTimeline(
            @PathVariable String ticker,
            @RequestParam(required = false) Integer limit
    ) {
        return ResponseEntity.ok(
                ApiResponse.success(timelineService.getTimeline(ticker, limit))
        );
    }
}
