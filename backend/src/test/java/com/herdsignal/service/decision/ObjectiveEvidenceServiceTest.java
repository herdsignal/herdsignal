package com.herdsignal.service.decision;

import com.herdsignal.dto.HerdObservationResponse;
import com.herdsignal.service.HerdObservationService;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ObjectiveEvidenceServiceTest {
    private static final Clock CLOCK = Clock.fixed(
            Instant.parse("2026-08-03T12:00:00Z"), ZoneOffset.UTC);

    @Test
    void exposesChartCrowdAndKeepsUnsupportedAreasAsNoView() {
        HerdObservationService observations = mock(HerdObservationService.class);
        when(observations.getLatest("NVDA")).thenReturn(available());
        ObjectiveEvidenceService service = new ObjectiveEvidenceService(
                observations, new EvidenceGate(), CLOCK);

        ObjectiveReviewResponse response = service.review("NVDA");

        assertThat(response.status()).isEqualTo("AVAILABLE");
        assertThat(response.directionPrediction()).isFalse();
        assertThat(response.operationalAction()).isEqualTo("OBSERVE");
        assertThat(response.operationalActionRatio()).isZero();
        assertThat(response.assessments())
                .filteredOn(item -> item.area() == DecisionArea.CHART_CROWD)
                .singleElement()
                .extracting(DecisionAreaAssessment::status)
                .isEqualTo(AssessmentStatus.AVAILABLE);
        assertThat(response.assessments())
                .filteredOn(item -> item.area() == DecisionArea.BUSINESS_HEALTH)
                .singleElement()
                .extracting(DecisionAreaAssessment::status)
                .isEqualTo(AssessmentStatus.NO_VIEW);
    }

    @Test
    void staleRequiredStateBlocksObjectiveReview() {
        HerdObservationService observations = mock(HerdObservationService.class);
        HerdObservationResponse stale = withFreshness(available(), "STALE");
        when(observations.getLatest("NVDA")).thenReturn(stale);
        ObjectiveEvidenceService service = new ObjectiveEvidenceService(
                observations, new EvidenceGate(), CLOCK);

        ObjectiveReviewResponse response = service.review("NVDA");

        assertThat(response.status()).isEqualTo("INSUFFICIENT_DATA");
        assertThat(response.dataGate().reasons())
                .contains("OBS.STATE_SCORE:REQUIRED_FACT_UNAVAILABLE");
    }

    private HerdObservationResponse available() {
        return new HerdObservationResponse(
                "AVAILABLE", "FRESH", 1, "NVDA", "NVIDIA", "NVIDIA Corp",
                "Technology", null, "PUBLIC_RESEARCH_ONLY", "STATE_ONLY", "V1",
                "HERD_STATE_S1", "HERD_TRANSITION_S1", LocalDate.of(2026, 8, 1),
                LocalDate.of(2026, 8, 1), OffsetDateTime.parse("2026-08-02T02:00:00Z"),
                new BigDecimal("72"), "DRIFT", "STABLE", "STABLE", false,
                new BigDecimal("4"), new BigDecimal("8"),
                new HerdObservationResponse.FamilyScores(
                        new BigDecimal("80"), new BigDecimal("70"),
                        new BigDecimal("65"), new BigDecimal("55")),
                new BigDecimal("30"), "SMH", BigDecimal.ONE,
                false, "HOLD", BigDecimal.ZERO, false);
    }

    private HerdObservationResponse withFreshness(HerdObservationResponse row, String freshness) {
        return new HerdObservationResponse(
                row.availabilityStatus(), freshness, row.businessSessionsOld(), row.ticker(),
                row.label(), row.companyName(), row.sector(), row.logoUrl(), row.scope(),
                row.claimCode(), row.schemaVersion(), row.stateModelVersion(),
                row.transitionModelVersion(), row.observationDate(), row.lastObservedSession(),
                row.generatedAt(), row.stateScore(), row.stage(), row.transition(),
                row.rawTransition(), row.transitionEvent(), row.delta4w(), row.delta13w(),
                row.families(), row.downsideRiskContext(), row.sectorEtf(),
                row.referenceCoverageFraction(), row.directionPrediction(),
                row.operationalAction(), row.operationalActionRatio(), row.survivorshipSafe());
    }
}
