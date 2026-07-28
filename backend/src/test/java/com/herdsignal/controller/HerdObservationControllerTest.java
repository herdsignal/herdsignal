package com.herdsignal.controller;

import com.herdsignal.dto.HerdObservationBatchResponse;
import com.herdsignal.dto.HerdObservationResponse;
import com.herdsignal.dto.HerdPriceTimelinePoint;
import com.herdsignal.dto.HerdPriceTimelineResponse;
import com.herdsignal.dto.HerdEpisodeStudyResponse;
import com.herdsignal.dto.HistoricalS1ContextResponse;
import com.herdsignal.dto.HistoricalS1ContextSummary;
import com.herdsignal.exception.GlobalExceptionHandler;
import com.herdsignal.service.HerdObservationService;
import com.herdsignal.service.HerdEpisodeStudyService;
import com.herdsignal.service.HerdPriceTimelineService;
import com.herdsignal.service.HistoricalS1ContextService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class HerdObservationControllerTest {
    private HerdObservationService service;
    private HerdPriceTimelineService timelineService;
    private HerdEpisodeStudyService episodeStudyService;
    private HistoricalS1ContextService historicalS1ContextService;
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        service = mock(HerdObservationService.class);
        timelineService = mock(HerdPriceTimelineService.class);
        episodeStudyService = mock(HerdEpisodeStudyService.class);
        historicalS1ContextService = mock(HistoricalS1ContextService.class);
        mockMvc = MockMvcBuilders
                .standaloneSetup(new HerdObservationController(
                        service,
                        timelineService,
                        episodeStudyService,
                        historicalS1ContextService
                ))
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    @Test
    void latestEndpointKeepsStateOnlyBoundary() throws Exception {
        when(service.getLatest("SPY")).thenReturn(unavailable());

        mockMvc.perform(get("/api/observations/SPY"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.availabilityStatus")
                        .value("UNAVAILABLE"))
                .andExpect(jsonPath("$.data.operationalAction").value("HOLD"))
                .andExpect(jsonPath("$.data.operationalActionRatio").value(0));
    }

    @Test
    void invalidHistoryLimitUsesCommonBadRequestEnvelope() throws Exception {
        when(service.getHistory("SPY", 999))
                .thenThrow(new IllegalArgumentException("limit 오류"));

        mockMvc.perform(get("/api/observations/SPY/history?limit=999"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("limit 오류"));
    }

    @Test
    void batchEndpointReturnsRequestedObservations() throws Exception {
        when(service.getLatestBatch(List.of("NVDA", "AAPL")))
                .thenReturn(new HerdObservationBatchResponse(
                        2,
                        0,
                        List.of(unavailable("NVDA"), unavailable("AAPL"))
                ));

        mockMvc.perform(get("/api/observations?tickers=NVDA,AAPL"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.requestedCount").value(2))
                .andExpect(jsonPath("$.data.availableCount").value(0))
                .andExpect(jsonPath("$.data.observations[0].ticker")
                        .value("NVDA"));
    }

    @Test
    void timelineEndpointExposesJoinedPriceAndHerdContract() throws Exception {
        when(timelineService.getTimeline("NVDA", 52))
                .thenReturn(new HerdPriceTimelineResponse(
                        "AVAILABLE",
                        "NVDA",
                        "HERD_STATE_S1",
                        "ADJUSTED_CLOSE",
                        1,
                        1,
                        List.of(new HerdPriceTimelinePoint(
                                LocalDate.of(2026, 7, 24),
                                LocalDate.of(2026, 7, 24),
                                new BigDecimal("175.50"),
                                new BigDecimal("64"),
                                "DRIFT",
                                "NEUTRAL",
                                false
                        ))
                ));

        mockMvc.perform(get("/api/observations/NVDA/timeline?limit=52"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.priceField")
                        .value("ADJUSTED_CLOSE"))
                .andExpect(jsonPath("$.data.points[0].marketSession[0]")
                        .value(2026))
                .andExpect(jsonPath("$.data.points[0].adjustedClose")
                        .value(175.5))
                .andExpect(jsonPath("$.data.points[0].herdScore")
                        .value(64));
    }

    @Test
    void episodeEndpointKeepsInsufficientSamplesExplicit() throws Exception {
        when(episodeStudyService.studyCurrentStage("NVDA"))
                .thenReturn(new HerdEpisodeStudyResponse(
                        "AVAILABLE",
                        "INSUFFICIENT_SAMPLE",
                        "NVDA",
                        "RUSH",
                        "HERD_STATE_S1",
                        5,
                        2,
                        List.of(),
                        List.of()
                ));

        mockMvc.perform(get("/api/observations/NVDA/episodes"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.herdStage").value("RUSH"))
                .andExpect(jsonPath("$.data.evidenceStatus")
                        .value("INSUFFICIENT_SAMPLE"))
                .andExpect(jsonPath("$.data.minimumCompletedEpisodes")
                        .value(5));
    }

    @Test
    void historicalContextEndpointKeepsDescriptiveBoundaryExplicit() throws Exception {
        when(historicalS1ContextService.getCurrentStageContext("NVDA"))
                .thenReturn(new HistoricalS1ContextResponse(
                        "AVAILABLE",
                        "DESCRIPTIVE_ONLY",
                        "TICKER_HISTORY",
                        "NVDA",
                        "RUSH",
                        "HERD_STATE_S1",
                        LocalDate.of(2013, 10, 18),
                        LocalDate.of(2026, 6, 12),
                        false,
                        5,
                        12,
                        List.of(new HistoricalS1ContextSummary(
                                21,
                                12,
                                new BigDecimal("2.40"),
                                new BigDecimal("58.30"),
                                new BigDecimal("8.10"),
                                new BigDecimal("-6.20")
                        )),
                        false,
                        "HOLD",
                        0
                ));

        mockMvc.perform(get("/api/observations/NVDA/historical-context"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.contextScope")
                        .value("TICKER_HISTORY"))
                .andExpect(jsonPath("$.data.survivorshipSafe").value(false))
                .andExpect(jsonPath("$.data.directionPrediction").value(false))
                .andExpect(jsonPath("$.data.operationalAction").value("HOLD"))
                .andExpect(jsonPath("$.data.operationalActionRatio").value(0));
    }

    private HerdObservationResponse unavailable() {
        return unavailable("SPY");
    }

    private HerdObservationResponse unavailable(String ticker) {
        return new HerdObservationResponse(
                "UNAVAILABLE",
                "UNAVAILABLE",
                null,
                ticker,
                "SPY".equals(ticker) ? "S&P 500 군중 상태" : null,
                null,
                null,
                null,
                null,
                null,
                null,
                "HERD_STATE_S1",
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                false,
                null,
                null,
                null,
                null,
                null,
                null,
                false,
                "HOLD",
                BigDecimal.ZERO,
                false
        );
    }
}
