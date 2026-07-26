package com.herdsignal.service;

import com.herdsignal.domain.*;
import com.herdsignal.dto.ObservationChangesResponse;
import com.herdsignal.repository.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class ObservationChangeServiceTest {
    private HerdObservationRepository observationRepository;
    private UserObservationReceiptRepository receiptRepository;
    private UserPortfolioRepository portfolioRepository;
    private UserWatchlistRepository watchlistRepository;
    private StockRepository stockRepository;
    private ObservationChangeService service;

    @BeforeEach
    void setUp() {
        observationRepository = mock(HerdObservationRepository.class);
        receiptRepository = mock(UserObservationReceiptRepository.class);
        portfolioRepository = mock(UserPortfolioRepository.class);
        watchlistRepository = mock(UserWatchlistRepository.class);
        stockRepository = mock(StockRepository.class);
        service = new ObservationChangeService(
                observationRepository,
                receiptRepository,
                portfolioRepository,
                watchlistRepository,
                stockRepository
        );
    }

    @Test
    void derivesOnlyConfirmedTransitionsAndStageChangesForTrackedStocks() {
        when(portfolioRepository.findByUserId("user"))
                .thenReturn(List.of(UserPortfolio.builder().ticker("NVDA").build()));
        when(watchlistRepository.findByUserId("user"))
                .thenReturn(List.of(UserWatchlist.builder().ticker("NVDA").build()));
        HerdObservation latest = observation(
                LocalDate.of(2026, 7, 24),
                "DRIFT",
                "COOLING",
                true
        );
        when(observationRepository.findLatestByTickersAndStateModelVersion(
                List.of("NVDA"),
                "HERD_STATE_S1"
        )).thenReturn(List.of(latest));
        when(receiptRepository.findByUserId("user")).thenReturn(List.of());
        when(stockRepository.findByTickerIn(List.of("NVDA")))
                .thenReturn(List.of(Stock.builder()
                        .ticker("NVDA")
                        .name("NVIDIA Corporation")
                        .sector("Technology")
                        .build()));
        when(observationRepository.findTrackedHistorySince(
                eq(List.of("NVDA")),
                eq("HERD_STATE_S1"),
                any(LocalDate.class)
        )).thenReturn(List.of(
                observation(LocalDate.of(2026, 7, 10), "CALM", "NEUTRAL", false),
                observation(LocalDate.of(2026, 7, 17), "DRIFT", "NEUTRAL", false),
                latest
        ));

        ObservationChangesResponse response = service.getChanges("user", 50);

        assertThat(response.trackedTickerCount()).isEqualTo(1);
        assertThat(response.unreadCount()).isEqualTo(2);
        assertThat(response.events())
                .extracting(event -> event.eventType())
                .containsExactly("TRANSITION", "STAGE_CHANGE");
        assertThat(response.events().get(0).transition()).isEqualTo("COOLING");
        assertThat(response.events().get(1).previousStage()).isEqualTo("CALM");
        assertThat(response.events().get(1).stage()).isEqualTo("DRIFT");
        assertThat(response.events()).allMatch(event -> event.unread());
    }

    @Test
    void countOnlyModeDoesNotReturnEventPayload() {
        when(portfolioRepository.findByUserId("user")).thenReturn(List.of());
        when(watchlistRepository.findByUserId("user")).thenReturn(List.of());

        ObservationChangesResponse response = service.getChanges("user", 0);

        assertThat(response.unreadCount()).isZero();
        assertThat(response.events()).isEmpty();
        verifyNoInteractions(observationRepository);
    }

    @Test
    void markingSeenIsMonotonicAndCannotExceedLatestObservation() {
        when(portfolioRepository.existsByUserIdAndTicker("user", "NVDA"))
                .thenReturn(true);
        HerdObservation latest = observation(
                LocalDate.of(2026, 7, 24),
                "DRIFT",
                "NEUTRAL",
                false
        );
        when(observationRepository
                .findTopByTickerAndStateModelVersionOrderByObservationDateDesc(
                        "NVDA",
                        "HERD_STATE_S1"
                ))
                .thenReturn(Optional.of(latest));
        when(receiptRepository.findByUserIdAndTicker("user", "NVDA"))
                .thenReturn(Optional.empty());

        service.markTickerSeen(
                "user",
                "nvda",
                LocalDate.of(2026, 8, 31)
        );

        var captor = org.mockito.ArgumentCaptor
                .forClass(UserObservationReceipt.class);
        verify(receiptRepository).save(captor.capture());
        assertThat(captor.getValue().getSeenThroughDate())
                .isEqualTo(LocalDate.of(2026, 7, 24));
    }

    private HerdObservation observation(
            LocalDate date,
            String stage,
            String transition,
            boolean transitionEvent
    ) {
        return HerdObservation.builder()
                .ticker("NVDA")
                .stateModelVersion("HERD_STATE_S1")
                .observationDate(date)
                .lastObservedSession(date)
                .stateScore(new BigDecimal("63"))
                .herdStage(stage)
                .transitionCode(transition)
                .transitionEvent(transitionEvent)
                .delta4w(new BigDecimal("6"))
                .generatedAt(LocalDateTime.of(2026, 7, 25, 0, 0))
                .build();
    }
}
