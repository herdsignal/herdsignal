package com.herdsignal.controller;

import com.herdsignal.dto.HerdObservationResponse;
import com.herdsignal.exception.GlobalExceptionHandler;
import com.herdsignal.service.HerdObservationService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.math.BigDecimal;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class HerdObservationControllerTest {
    private HerdObservationService service;
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        service = mock(HerdObservationService.class);
        mockMvc = MockMvcBuilders
                .standaloneSetup(new HerdObservationController(service))
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

    private HerdObservationResponse unavailable() {
        return new HerdObservationResponse(
                "UNAVAILABLE",
                "UNAVAILABLE",
                null,
                "SPY",
                "S&P 500 군중 상태",
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
