package com.herdsignal.repository;

import com.herdsignal.domain.HerdObservation;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.data.domain.PageRequest;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
class HerdObservationRepositoryTest {
    @Autowired
    private HerdObservationRepository repository;

    @Test
    void readsLatestAndBoundedHistoryWithoutUsingV4Table() {
        repository.save(observation(LocalDate.of(2026, 7, 17)));
        repository.save(observation(LocalDate.of(2026, 7, 24)));

        HerdObservation latest = repository
                .findTopByTickerAndStateModelVersionOrderByObservationDateDesc(
                        "AAPL",
                        "HERD_STATE_S1"
                )
                .orElseThrow();

        assertThat(latest.getObservationDate())
                .isEqualTo(LocalDate.of(2026, 7, 24));
        assertThat(repository
                .findByTickerAndStateModelVersionOrderByObservationDateDesc(
                        "AAPL",
                        "HERD_STATE_S1",
                        PageRequest.of(0, 1)
                ))
                .extracting(HerdObservation::getObservationDate)
                .containsExactly(LocalDate.of(2026, 7, 24));
    }

    private HerdObservation observation(LocalDate date) {
        LocalDateTime now = LocalDateTime.of(2026, 7, 25, 0, 0);
        return HerdObservation.builder()
                .ticker("AAPL")
                .schemaVersion("HERD_OBSERVATION_S1_SERVICE_V1")
                .stateModelVersion("HERD_STATE_S1")
                .transitionModelVersion("HERD_TRANSITION_S1")
                .observationDate(date)
                .lastObservedSession(date)
                .generatedAt(now)
                .sourceScope("EQUITY")
                .stateScore(new BigDecimal("62.5000"))
                .herdStage("DRIFT")
                .transitionCode("NEUTRAL")
                .rawTransitionCode("NEUTRAL")
                .transitionEvent(false)
                .delta4w(BigDecimal.ZERO)
                .delta13w(BigDecimal.ZERO)
                .priceExtension(new BigDecimal("70.0000"))
                .trendPosition(new BigDecimal("65.0000"))
                .relativePosition(new BigDecimal("60.0000"))
                .participation(new BigDecimal("55.0000"))
                .downsideRiskContext(new BigDecimal("35.0000"))
                .sectorEtf("XLK")
                .directionPrediction(false)
                .operationalAction("HOLD")
                .operationalActionRatio(BigDecimal.ZERO)
                .survivorshipSafe(false)
                .createdAt(now)
                .updatedAt(now)
                .build();
    }
}
