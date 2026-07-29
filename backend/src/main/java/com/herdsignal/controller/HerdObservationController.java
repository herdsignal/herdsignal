package com.herdsignal.controller;

import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.HerdObservationBatchResponse;
import com.herdsignal.dto.HerdObservationHistoryResponse;
import com.herdsignal.dto.HerdObservationResponse;
import com.herdsignal.dto.HerdPriceTimelineResponse;
import com.herdsignal.dto.HerdEpisodeStudyResponse;
import com.herdsignal.dto.HistoricalS1ContextResponse;
import com.herdsignal.service.HerdEpisodeStudyService;
import com.herdsignal.service.HistoricalS1ContextService;
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
    private final HerdEpisodeStudyService episodeStudyService;
    private final HistoricalS1ContextService historicalContextService;

    @GetMapping
    public ResponseEntity<ApiResponse<HerdObservationBatchResponse>> getLatestBatch(
            @RequestParam String tickers
    ) {
        return ResponseEntity.ok(ApiResponse.success(
                service.getLatestBatch(Arrays.asList(tickers.split(",")))
        ));
    }

    @GetMapping("/daily")
    public ResponseEntity<ApiResponse<HerdObservationBatchResponse>> getLatestDailyBatch(
            @RequestParam String tickers
    ) {
        return ResponseEntity.ok(ApiResponse.success(
                service.getLatestDailyBatch(Arrays.asList(tickers.split(",")))
        ));
    }

    @GetMapping("/{ticker}")
    public ResponseEntity<ApiResponse<HerdObservationResponse>> getLatest(
            @PathVariable String ticker
    ) {
        return ResponseEntity.ok(ApiResponse.success(service.getLatest(ticker)));
    }

    @GetMapping("/daily/{ticker}")
    public ResponseEntity<ApiResponse<HerdObservationResponse>> getLatestDaily(
            @PathVariable String ticker
    ) {
        return ResponseEntity.ok(ApiResponse.success(
                service.getLatestDaily(ticker)
        ));
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

    @GetMapping("/{ticker}/episodes")
    public ResponseEntity<ApiResponse<HerdEpisodeStudyResponse>> getEpisodes(
            @PathVariable String ticker
    ) {
        return ResponseEntity.ok(ApiResponse.success(
                episodeStudyService.studyCurrentStage(ticker)
        ));
    }

    @GetMapping("/{ticker}/historical-context")
    public ResponseEntity<ApiResponse<HistoricalS1ContextResponse>> getHistoricalContext(
            @PathVariable String ticker
    ) {
        return ResponseEntity.ok(ApiResponse.success(
                historicalContextService.getCurrentStageContext(ticker)
        ));
    }
}
