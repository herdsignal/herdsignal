package com.herdsignal.service;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.domain.HerdObservation;
import com.herdsignal.dto.HerdEpisodeStudyResponse;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.HerdObservationRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.data.domain.Pageable;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class HerdEpisodeStudyServiceTest {
    private HerdObservationRepository observationRepository;
    private DailyPriceRepository priceRepository;
    private HerdEpisodeStudyService service;

    @BeforeEach
    void setUp() {
        observationRepository = mock(HerdObservationRepository.class);
        priceRepository = mock(DailyPriceRepository.class);
        service = new HerdEpisodeStudyService(
                observationRepository,
                priceRepository
        );
    }

    @Test
    void countsStageEntriesInsteadOfEveryWeeklyObservation() {
        List<HerdObservation> observations = List.of(
                observation("2026-06-26", "DRIFT", "65"),
                observation("2026-06-19", "DRIFT", "63"),
                observation("2026-06-12", "CALM", "58"),
                observation("2026-06-05", "DRIFT", "62"),
                observation("2026-05-29", "DRIFT", "61"),
                observation("2026-05-22", "CALM", "55")
        );
        when(observationRepository
                .findByTickerAndStateModelVersionOrderByObservationDateDesc(
                        eq("NVDA"),
                        eq("HERD_STATE_S1"),
                        any(Pageable.class)
                ))
                .thenReturn(observations);
        List<DailyPrice> prices = prices(
                LocalDate.of(2026, 5, 29),
                90
        );
        when(priceRepository
                .findTopByTickerAndClosePriceIsNotNullOrderByPriceDateDesc(
                        "NVDA"
                ))
                .thenReturn(Optional.of(prices.get(prices.size() - 1)));
        when(priceRepository.findPricesForTickerBetween(
                "NVDA",
                LocalDate.of(2026, 5, 29),
                prices.get(prices.size() - 1).getPriceDate()
        )).thenReturn(prices);

        HerdEpisodeStudyResponse response = service.studyCurrentStage("nvda");

        assertThat(response.herdStage()).isEqualTo("DRIFT");
        assertThat(response.episodeCount()).isEqualTo(2);
        assertThat(response.evidenceStatus()).isEqualTo("INSUFFICIENT_SAMPLE");
        assertThat(response.summaries().get(0).completedCount()).isEqualTo(2);
        assertThat(response.summaries().get(0).medianReturnPct()).isNotNull();
    }

    @Test
    void excludesLeftCensoredFirstObservedStage() {
        HerdObservation latest = observation("2026-07-24", "CALM", "51");
        HerdObservation earlier = observation("2026-07-17", "CALM", "50");
        when(observationRepository
                .findByTickerAndStateModelVersionOrderByObservationDateDesc(
                        eq("SPY"),
                        eq("HERD_STATE_S1"),
                        any(Pageable.class)
                ))
                .thenReturn(List.of(latest, earlier));

        HerdEpisodeStudyResponse response = service.studyCurrentStage("SPY");

        assertThat(response.episodeCount()).isZero();
        assertThat(response.evidenceStatus()).isEqualTo("INSUFFICIENT_SAMPLE");
    }

    private HerdObservation observation(
            String date,
            String stage,
            String score
    ) {
        HerdObservation observation = mock(HerdObservation.class);
        LocalDate localDate = LocalDate.parse(date);
        when(observation.getObservationDate()).thenReturn(localDate);
        when(observation.getLastObservedSession()).thenReturn(localDate);
        when(observation.getHerdStage()).thenReturn(stage);
        when(observation.getStateScore()).thenReturn(new BigDecimal(score));
        return observation;
    }

    private List<DailyPrice> prices(LocalDate start, int days) {
        List<DailyPrice> prices = new ArrayList<>();
        for (int day = 0; day < days; day++) {
            LocalDate date = start.plusDays(day);
            DailyPrice price = mock(DailyPrice.class);
            when(price.getPriceDate()).thenReturn(date);
            when(price.getClosePrice()).thenReturn(
                    BigDecimal.valueOf(100 + day)
            );
            prices.add(price);
        }
        return prices;
    }
}
