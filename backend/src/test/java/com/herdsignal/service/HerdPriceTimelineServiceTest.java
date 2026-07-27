package com.herdsignal.service;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.domain.HerdObservation;
import com.herdsignal.dto.HerdPriceTimelineResponse;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.HerdObservationRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.data.domain.Pageable;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class HerdPriceTimelineServiceTest {
    private HerdObservationRepository observationRepository;
    private DailyPriceRepository priceRepository;
    private HerdPriceTimelineService service;

    @BeforeEach
    void setUp() {
        observationRepository = mock(HerdObservationRepository.class);
        priceRepository = mock(DailyPriceRepository.class);
        service = new HerdPriceTimelineService(
                observationRepository,
                priceRepository
        );
    }

    @Test
    void joinsExactMarketSessionsAndReturnsChronologicalPoints() {
        HerdObservation latest = observation(
                LocalDate.of(2026, 7, 24),
                "64.0",
                "DRIFT"
        );
        HerdObservation earlier = observation(
                LocalDate.of(2026, 7, 17),
                "55.0",
                "CALM"
        );
        DailyPrice latestPrice = price(
                LocalDate.of(2026, 7, 24),
                "175.50"
        );
        when(observationRepository
                .findByTickerAndStateModelVersionOrderByObservationDateDesc(
                        eq("NVDA"),
                        eq("HERD_STATE_S1"),
                        any(Pageable.class)
                ))
                .thenReturn(List.of(latest, earlier));
        when(priceRepository.findPricesForTickerBetween(
                "NVDA",
                LocalDate.of(2026, 7, 17),
                LocalDate.of(2026, 7, 24)
        )).thenReturn(List.of(latestPrice));

        HerdPriceTimelineResponse response = service.getTimeline(" nvda ", 20);

        assertThat(response.availabilityStatus()).isEqualTo("AVAILABLE");
        assertThat(response.priceField()).isEqualTo("ADJUSTED_CLOSE");
        assertThat(response.observationCount()).isEqualTo(2);
        assertThat(response.pricedObservationCount()).isEqualTo(1);
        assertThat(response.points())
                .extracting(point -> point.observationDate())
                .containsExactly(
                        LocalDate.of(2026, 7, 17),
                        LocalDate.of(2026, 7, 24)
                );
        assertThat(response.points().get(0).adjustedClose()).isNull();
        assertThat(response.points().get(1).adjustedClose())
                .isEqualByComparingTo("175.50");
    }

    @Test
    void returnsExplicitUnavailableWithoutPriceLookup() {
        when(observationRepository
                .findByTickerAndStateModelVersionOrderByObservationDateDesc(
                        eq("SPY"),
                        eq("HERD_STATE_S1"),
                        any(Pageable.class)
                ))
                .thenReturn(List.of());

        HerdPriceTimelineResponse response = service.getTimeline("SPY", null);

        assertThat(response.availabilityStatus()).isEqualTo("UNAVAILABLE");
        assertThat(response.points()).isEmpty();
        verifyNoInteractions(priceRepository);
    }

    @Test
    void rejectsInvalidTickerAndLimit() {
        assertThatThrownBy(() -> service.getTimeline("../NVDA", 20))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> service.getTimeline("NVDA", 261))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("260");
        verifyNoInteractions(observationRepository, priceRepository);
    }

    private HerdObservation observation(
            LocalDate date,
            String score,
            String stage
    ) {
        HerdObservation observation = mock(HerdObservation.class);
        when(observation.getObservationDate()).thenReturn(date);
        when(observation.getLastObservedSession()).thenReturn(date);
        when(observation.getStateScore()).thenReturn(new BigDecimal(score));
        when(observation.getHerdStage()).thenReturn(stage);
        when(observation.getTransitionCode()).thenReturn("NEUTRAL");
        when(observation.isTransitionEvent()).thenReturn(false);
        return observation;
    }

    private DailyPrice price(LocalDate date, String close) {
        DailyPrice price = mock(DailyPrice.class);
        when(price.getPriceDate()).thenReturn(date);
        when(price.getClosePrice()).thenReturn(new BigDecimal(close));
        return price;
    }
}
