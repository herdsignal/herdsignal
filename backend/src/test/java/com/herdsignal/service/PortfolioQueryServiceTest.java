package com.herdsignal.service;

import com.herdsignal.repository.PortfolioHistoryRepository;
import com.herdsignal.repository.UserPortfolioRepository;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class PortfolioQueryServiceTest {

    @Test
    void historyWindowUsesTheSameUsMarketSessionAsTheSummary() {
        PortfolioHistoryRepository historyRepository = mock(PortfolioHistoryRepository.class);
        PortfolioCashService cashService = mock(PortfolioCashService.class);
        UsMarketSessionClock marketClock = new UsMarketSessionClock(
                Clock.fixed(Instant.parse("2026-07-24T14:00:00Z"), ZoneOffset.UTC)
        );
        PortfolioQueryService service = new PortfolioQueryService(
                mock(UserPortfolioRepository.class),
                historyRepository,
                mock(PortfolioHoldingValuationService.class),
                cashService,
                marketClock
        );
        LocalDate sessionDate = LocalDate.of(2026, 7, 23);
        LocalDate startDate = sessionDate.minusDays(30);
        when(historyRepository.findByUserIdAndSnapshotDateBetweenOrderBySnapshotDateAsc(
                "user-1", startDate, sessionDate
        )).thenReturn(List.of());
        when(cashService.historyAtPortfolioDates(
                "user-1", startDate, sessionDate, List.of()
        )).thenReturn(Map.of());

        service.getHistory("user-1", "month");

        verify(historyRepository).findByUserIdAndSnapshotDateBetweenOrderBySnapshotDateAsc(
                "user-1", startDate, sessionDate
        );
    }
}
