package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.domain.HerdObservation;
import com.herdsignal.dto.HistoricalS1ContextResponse;
import com.herdsignal.repository.HerdObservationRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class HistoricalS1ContextServiceTest {
    private HerdObservationRepository repository;
    private HistoricalS1ContextService service;

    @BeforeEach
    void setUp() {
        repository = mock(HerdObservationRepository.class);
        service = new HistoricalS1ContextService(
                repository,
                new ObjectMapper()
        );
    }

    @Test
    void returnsDescriptiveContextWithoutActionAuthority() {
        when(repository
                .findTopByTickerAndStateModelVersionOrderByObservationDateDesc(
                        "NVDA",
                        "HERD_STATE_S1"
                ))
                .thenReturn(Optional.of(HerdObservation.builder()
                        .ticker("NVDA")
                        .herdStage("RUSH")
                        .build()));

        HistoricalS1ContextResponse response =
                service.getCurrentStageContext("nvda");

        assertThat(response.availabilityStatus()).isEqualTo("AVAILABLE");
        assertThat(response.evidenceStatus()).isEqualTo("DESCRIPTIVE_ONLY");
        assertThat(response.summaries()).isNotEmpty();
        assertThat(response.directionPrediction()).isFalse();
        assertThat(response.operationalAction()).isEqualTo("HOLD");
        assertThat(response.operationalActionRatio()).isZero();
        assertThat(response.survivorshipSafe()).isFalse();
    }

    @Test
    void returnsUnavailableWhenNoCurrentObservationExists() {
        when(repository
                .findTopByTickerAndStateModelVersionOrderByObservationDateDesc(
                        "NVDA",
                        "HERD_STATE_S1"
                ))
                .thenReturn(Optional.empty());

        HistoricalS1ContextResponse response =
                service.getCurrentStageContext("NVDA");

        assertThat(response.availabilityStatus()).isEqualTo("UNAVAILABLE");
        assertThat(response.operationalAction()).isEqualTo("HOLD");
    }

    @Test
    void rejectsInvalidTickerBeforeRepositoryLookup() {
        assertThatThrownBy(() -> service.getCurrentStageContext("../NVDA"))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
