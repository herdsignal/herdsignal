package com.herdsignal.controller;

import com.herdsignal.dto.PortfolioLedgerEntryResponse;
import com.herdsignal.exception.GlobalExceptionHandler;
import com.herdsignal.service.CurrentUserService;
import com.herdsignal.service.PortfolioLedgerService;
import com.herdsignal.service.PortfolioLedgerValuationService;
import com.herdsignal.service.PortfolioOpeningSnapshotService;
import com.herdsignal.service.PortfolioPerformanceService;
import com.herdsignal.service.PortfolioSourceReconciliationService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class PortfolioLedgerControllerTest {

    private PortfolioLedgerService service;
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        service = mock(PortfolioLedgerService.class);
        PortfolioLedgerValuationService valuationService =
                mock(PortfolioLedgerValuationService.class);
        PortfolioPerformanceService performanceService =
                mock(PortfolioPerformanceService.class);
        PortfolioOpeningSnapshotService openingSnapshotService =
                mock(PortfolioOpeningSnapshotService.class);
        PortfolioSourceReconciliationService reconciliationService =
                mock(PortfolioSourceReconciliationService.class);
        CurrentUserService currentUserService = mock(CurrentUserService.class);
        when(currentUserService.requireUserId()).thenReturn("user-a");
        mockMvc = MockMvcBuilders
                .standaloneSetup(new PortfolioLedgerController(
                        service,
                        valuationService,
                        performanceService,
                        openingSnapshotService,
                        reconciliationService,
                        currentUserService
                ))
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    @Test
    void returnsOnlyTheCurrentUsersLedgerView() throws Exception {
        when(service.getEntries("user-a", "NVDA")).thenReturn(List.of(
                PortfolioLedgerEntryResponse.builder()
                        .id(1L)
                        .entryType("BUY")
                        .ticker("NVDA")
                        .occurredOn(LocalDate.of(2026, 1, 2))
                        .grossAmount(new BigDecimal("100.00"))
                        .cashEffect(new BigDecimal("-100.00"))
                        .currency("USD")
                        .build()
        ));

        mockMvc.perform(get("/api/portfolio/ledger?ticker=NVDA"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[0].ticker").value("NVDA"))
                .andExpect(jsonPath("$.data[0].cashEffect").value(-100.0));
    }

    @Test
    void createsAnAccountScopedLedgerEntry() throws Exception {
        when(service.create(org.mockito.ArgumentMatchers.eq("user-a"), any()))
                .thenReturn(PortfolioLedgerEntryResponse.builder()
                        .id(2L)
                        .entryType("DEPOSIT")
                        .occurredOn(LocalDate.of(2026, 1, 2))
                        .grossAmount(new BigDecimal("500.00"))
                        .cashEffect(new BigDecimal("500.00"))
                        .currency("USD")
                        .build());

        mockMvc.perform(post("/api/portfolio/ledger")
                        .contentType("application/json")
                        .content("""
                                {
                                  "entryType": "DEPOSIT",
                                  "occurredOn": "2026-01-02",
                                  "amount": 500
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.entryType").value("DEPOSIT"))
                .andExpect(jsonPath("$.data.cashEffect").value(500.0));
    }

    @Test
    void deletesOnlyThroughTheCurrentUserBoundary() throws Exception {
        mockMvc.perform(delete("/api/portfolio/ledger/8"))
                .andExpect(status().isNoContent());

        verify(service).delete("user-a", 8L);
    }
}
