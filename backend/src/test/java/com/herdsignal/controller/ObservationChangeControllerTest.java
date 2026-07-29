package com.herdsignal.controller;

import com.herdsignal.dto.ObservationChangesResponse;
import com.herdsignal.exception.GlobalExceptionHandler;
import com.herdsignal.service.CurrentUserService;
import com.herdsignal.service.ObservationChangeService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.time.LocalDate;
import java.util.List;

import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class ObservationChangeControllerTest {
    private ObservationChangeService service;
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        service = mock(ObservationChangeService.class);
        CurrentUserService currentUserService = mock(CurrentUserService.class);
        when(currentUserService.requireUserId()).thenReturn("user");
        mockMvc = MockMvcBuilders
                .standaloneSetup(new ObservationChangeController(
                        service,
                        currentUserService
                ))
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    @Test
    void returnsAccountScopedObservationChanges() throws Exception {
        when(service.getChanges("user", 20)).thenReturn(
                new ObservationChangesResponse(
                        LocalDate.of(2026, 7, 24),
                        3,
                        2,
                        List.of(),
                        List.of()
                )
        );

        mockMvc.perform(get("/api/observation-changes?limit=20"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.trackedTickerCount").value(3))
                .andExpect(jsonPath("$.data.unreadCount").value(2));
    }

    @Test
    void marksOneTickerThroughAnExplicitObservationDate() throws Exception {
        mockMvc.perform(post("/api/observation-changes/NVDA/seen")
                        .contentType("application/json")
                        .content("""
                                {"seenThroughDate":"2026-07-24"}
                                """))
                .andExpect(status().isOk());

        verify(service).markTickerSeen(
                "user",
                "NVDA",
                LocalDate.of(2026, 7, 24)
        );
    }

    @Test
    void rejectsMissingSeenDate() throws Exception {
        mockMvc.perform(post("/api/observation-changes/NVDA/seen")
                        .contentType("application/json")
                        .content("{}"))
                .andExpect(status().isBadRequest());
        verifyNoInteractions(service);
    }
}
