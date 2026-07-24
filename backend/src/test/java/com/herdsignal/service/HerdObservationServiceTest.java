package com.herdsignal.service;

import com.herdsignal.domain.HerdObservation;
import com.herdsignal.domain.Stock;
import com.herdsignal.dto.HerdObservationBatchResponse;
import com.herdsignal.dto.HerdObservationHistoryResponse;
import com.herdsignal.dto.HerdObservationResponse;
import com.herdsignal.repository.HerdObservationRepository;
import com.herdsignal.repository.StockRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.data.domain.Pageable;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.*;

class HerdObservationServiceTest {
    private HerdObservationRepository repository;
    private StockRepository stockRepository;
    private HerdObservationService service;

    @BeforeEach
    void setUp() {
        repository = mock(HerdObservationRepository.class);
        stockRepository = mock(StockRepository.class);
        Clock clock = Clock.fixed(
                Instant.parse("2026-07-27T12:00:00Z"),
                ZoneOffset.UTC
        );
        service = new HerdObservationService(
                repository,
                stockRepository,
                new UsMarketSessionClock(clock)
        );
    }

    @Test
    void returnsFreshStateOnlyObservation() {
        HerdObservation row = observation(
                "SPY",
                LocalDate.of(2026, 7, 24),
                "MARKET_AGGREGATE"
        );
        when(repository
                .findTopByTickerAndStateModelVersionOrderByObservationDateDesc(
                        "SPY",
                        "HERD_STATE_S1"
                ))
                .thenReturn(Optional.of(row));
        when(stockRepository.findByTicker("SPY"))
                .thenReturn(Optional.of(stock("SPY", "SPDR S&P 500 ETF")));

        HerdObservationResponse response = service.getLatest(" spy ");

        assertThat(response.availabilityStatus()).isEqualTo("AVAILABLE");
        assertThat(response.freshnessStatus()).isEqualTo("FRESH");
        assertThat(response.businessSessionsOld()).isZero();
        assertThat(response.scope()).isEqualTo("MARKET_AGGREGATE");
        assertThat(response.companyName()).isEqualTo("SPDR S&P 500 ETF");
        assertThat(response.operationalAction()).isEqualTo("HOLD");
        assertThat(response.operationalActionRatio()).isEqualByComparingTo("0");
        assertThat(response.directionPrediction()).isFalse();
        assertThat(response.survivorshipSafe()).isFalse();
    }

    @Test
    void failsClosedEvenIfAStoredRowContainsActionFields() {
        HerdObservation row = observation(
                "AAPL",
                LocalDate.of(2026, 7, 24),
                "EQUITY"
        ).toBuilder()
                .directionPrediction(true)
                .operationalAction("SELL")
                .operationalActionRatio(new BigDecimal("0.1500"))
                .survivorshipSafe(true)
                .build();
        when(repository
                .findTopByTickerAndStateModelVersionOrderByObservationDateDesc(
                        "AAPL",
                        "HERD_STATE_S1"
                ))
                .thenReturn(Optional.of(row));

        HerdObservationResponse response = service.getLatest("AAPL");

        assertThat(response.operationalAction()).isEqualTo("HOLD");
        assertThat(response.operationalActionRatio()).isEqualByComparingTo("0");
        assertThat(response.directionPrediction()).isFalse();
        assertThat(response.survivorshipSafe()).isFalse();
    }

    @Test
    void marksOldLastObservedSessionAsStale() {
        HerdObservation row = observation(
                "NVDA",
                LocalDate.of(2026, 7, 20),
                "EQUITY"
        );
        when(repository
                .findTopByTickerAndStateModelVersionOrderByObservationDateDesc(
                        "NVDA",
                        "HERD_STATE_S1"
                ))
                .thenReturn(Optional.of(row));

        HerdObservationResponse response = service.getLatest("NVDA");

        assertThat(response.freshnessStatus()).isEqualTo("STALE");
        assertThat(response.businessSessionsOld()).isEqualTo(4);
    }

    @Test
    void missingObservationIsExplicitlyUnavailable() {
        when(repository
                .findTopByTickerAndStateModelVersionOrderByObservationDateDesc(
                        "SPY",
                        "HERD_STATE_S1"
                ))
                .thenReturn(Optional.empty());

        HerdObservationResponse response = service.getLatest("SPY");

        assertThat(response.availabilityStatus()).isEqualTo("UNAVAILABLE");
        assertThat(response.freshnessStatus()).isEqualTo("UNAVAILABLE");
        assertThat(response.label()).isEqualTo("S&P 500 군중 상태");
        assertThat(response.operationalAction()).isEqualTo("HOLD");
    }

    @Test
    void historyIsNewestFirstAndBounded() {
        when(repository
                .findByTickerAndStateModelVersionOrderByObservationDateDesc(
                        eq("AAPL"),
                        eq("HERD_STATE_S1"),
                        any(Pageable.class)
                ))
                .thenReturn(List.of(
                        observation("AAPL", LocalDate.of(2026, 7, 24), "EQUITY"),
                        observation("AAPL", LocalDate.of(2026, 7, 17), "EQUITY")
                ));

        HerdObservationHistoryResponse response = service.getHistory("aapl", 12);

        assertThat(response.availabilityStatus()).isEqualTo("AVAILABLE");
        assertThat(response.points())
                .extracting(point -> point.observationDate())
                .containsExactly(
                        LocalDate.of(2026, 7, 24),
                        LocalDate.of(2026, 7, 17)
                );
        ArgumentCaptor<Pageable> pageable = ArgumentCaptor.forClass(Pageable.class);
        verify(repository)
                .findByTickerAndStateModelVersionOrderByObservationDateDesc(
                        eq("AAPL"),
                        eq("HERD_STATE_S1"),
                        pageable.capture()
                );
        assertThat(pageable.getValue().getPageSize()).isEqualTo(12);
    }

    @Test
    void batchPreservesRequestOrderAndIncludesUnavailableStocks() {
        when(repository.findLatestByTickersAndStateModelVersion(
                List.of("NVDA", "AAPL"),
                "HERD_STATE_S1"
        )).thenReturn(List.of(
                observation("AAPL", LocalDate.of(2026, 7, 24), "EQUITY")
        ));
        when(stockRepository.findByTickerIn(List.of("NVDA", "AAPL")))
                .thenReturn(List.of(
                        stock("NVDA", "NVIDIA Corporation"),
                        stock("AAPL", "Apple Inc.")
                ));

        HerdObservationBatchResponse response = service.getLatestBatch(
                List.of(" nvda ", "AAPL", "NVDA")
        );

        assertThat(response.requestedCount()).isEqualTo(2);
        assertThat(response.availableCount()).isEqualTo(1);
        assertThat(response.observations())
                .extracting(HerdObservationResponse::ticker)
                .containsExactly("NVDA", "AAPL");
        assertThat(response.observations().get(0).availabilityStatus())
                .isEqualTo("UNAVAILABLE");
        assertThat(response.observations().get(0).companyName())
                .isEqualTo("NVIDIA Corporation");
        assertThat(response.observations().get(0).operationalAction())
                .isEqualTo("HOLD");
    }

    @Test
    void rejectsInvalidTickerAndUnboundedHistory() {
        assertThatThrownBy(() -> service.getLatest("../SPY"))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> service.getHistory("SPY", 261))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("260");
        assertThatThrownBy(() -> service.getLatestBatch(List.of()))
                .isInstanceOf(IllegalArgumentException.class);
        verifyNoInteractions(repository, stockRepository);
    }

    private HerdObservation observation(
            String ticker,
            LocalDate lastSession,
            String scope
    ) {
        return HerdObservation.builder()
                .id(1L)
                .ticker(ticker)
                .schemaVersion("HERD_OBSERVATION_S1_SERVICE_V1")
                .stateModelVersion("HERD_STATE_S1")
                .transitionModelVersion("HERD_TRANSITION_S1")
                .observationDate(lastSession)
                .lastObservedSession(lastSession)
                .generatedAt(LocalDateTime.of(2026, 7, 25, 0, 0))
                .sourceScope(scope)
                .displayLabel(
                        "SPY".equals(ticker) ? "S&P 500 군중 상태" : null
                )
                .claimCode(
                        "SPY".equals(ticker)
                                ? "CROWD_STATE_NOT_SPY_PRICE_SCORE"
                                : null
                )
                .stateScore(new BigDecimal("62.5000"))
                .herdStage("DRIFT")
                .transitionCode("NEUTRAL")
                .rawTransitionCode("NEUTRAL")
                .transitionEvent(false)
                .delta4w(new BigDecimal("1.2500"))
                .delta13w(new BigDecimal("3.5000"))
                .priceExtension(new BigDecimal("70.0000"))
                .trendPosition(new BigDecimal("65.0000"))
                .relativePosition(new BigDecimal("60.0000"))
                .participation(new BigDecimal("55.0000"))
                .downsideRiskContext(new BigDecimal("35.0000"))
                .sectorEtf("XLK")
                .referenceCoverageFraction(
                        "SPY".equals(ticker)
                                ? new BigDecimal("1.000000")
                                : null
                )
                .directionPrediction(false)
                .operationalAction("HOLD")
                .operationalActionRatio(BigDecimal.ZERO)
                .survivorshipSafe(false)
                .createdAt(LocalDateTime.of(2026, 7, 25, 0, 0))
                .updatedAt(LocalDateTime.of(2026, 7, 25, 0, 0))
                .build();
    }

    private Stock stock(String ticker, String name) {
        return Stock.builder()
                .ticker(ticker)
                .name(name)
                .sector("Technology")
                .logoUrl("https://example.com/" + ticker + ".png")
                .build();
    }
}
