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
import java.util.Optional;
import java.util.List;

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

    @Test
    void exposesVerifiedSecFactsWithoutPromotingRejectedBusinessDirection() {
        HerdObservationService observations = mock(HerdObservationService.class);
        when(observations.getLatest("NVDA")).thenReturn(available());
        PitBusinessEvidenceProvider business = (ticker, date) -> Optional.of(
                new BusinessEvidenceSnapshot(
                        "NVDA", "0001045810", LocalDate.of(2026, 6, 30),
                        "PIT_FACTS_READY", OffsetDateTime.parse("2026-05-20T20:35:52Z"),
                        "GENERAL", "HERD_SEC_PIT_BUSINESS_FACTS_V1:testhash",
                        new BigDecimal("0.85"), new BigDecimal("0.71"),
                        new BigDecimal("0.28"), new BigDecimal("0.60"),
                        new BigDecimal("102718000000"), new BigDecimal("0.24"),
                        new BigDecimal("-0.08")));
        ObjectiveEvidenceService service = new ObjectiveEvidenceService(
                observations, new EvidenceGate(), business, CLOCK);

        ObjectiveReviewResponse response = service.review("NVDA");

        assertThat(response.assessments())
                .filteredOn(item -> item.area() == DecisionArea.BUSINESS_HEALTH)
                .singleElement()
                .satisfies(item -> {
                    assertThat(item.status()).isEqualTo(AssessmentStatus.PARTIAL);
                    assertThat(item.limitations()).anyMatch(value -> value.contains("OOS"));
                });
        assertThat(response.evidencePacket().facts())
                .filteredOn(item -> item.id().equals("BUSINESS.PIT.REVENUE_YOY"))
                .singleElement()
                .satisfies(item -> {
                    assertThat(item.value()).isEqualTo("0.85");
                    assertThat(item.pointInTimeRequired()).isTrue();
                    assertThat(item.source()).isEqualTo("SEC_COMPANY_FACTS");
                    assertThat(item.sourceVersion()).endsWith(":testhash");
                });
        assertThat(response.directionPrediction()).isFalse();
        assertThat(response.operationalActionRatio()).isZero();
    }

    @Test
    void keepsSectorReferenceInsideChartCrowdAndMarketAreaAsNoView() {
        HerdObservationService observations = mock(HerdObservationService.class);
        when(observations.getLatest("NVDA")).thenReturn(available());
        ObjectiveEvidenceService service = new ObjectiveEvidenceService(
                observations, new EvidenceGate(), CLOCK);

        ObjectiveReviewResponse response = service.review("NVDA");

        assertThat(response.evidencePacket().facts())
                .filteredOn(item -> item.id().equals("OBS.SECTOR_REFERENCE"))
                .singleElement()
                .extracting(EvidenceFact::area)
                .isEqualTo(DecisionArea.CHART_CROWD);
        assertThat(response.assessments())
                .filteredOn(item -> item.area() == DecisionArea.MARKET_SECTOR)
                .singleElement()
                .extracting(DecisionAreaAssessment::status)
                .isEqualTo(AssessmentStatus.NO_VIEW);
    }

    @Test
    void exposesRecentReviewedGuidanceAsFactWithoutCreatingDirection() {
        HerdObservationService observations = mock(HerdObservationService.class);
        when(observations.getLatest("NVDA")).thenReturn(available());
        PitGuidanceEvidenceProvider guidance = (ticker, date) -> List.of(
                new GuidanceEvidenceFactSnapshot(
                        "binding-1", "NVDA", "0001045810", "0001",
                        OffsetDateTime.parse("2026-05-20T20:00:00Z"),
                        "https://www.sec.gov/example", "sourcehash", "HTML_TABLE",
                        "REVENUE", "FY2027", "NON_GAAP", "NOT_APPLICABLE", "USD",
                        new BigDecimal("100"), new BigDecimal("110"),
                        new BigDecimal("105"), "bindings:testhash"));
        ObjectiveEvidenceService service = new ObjectiveEvidenceService(
                observations, new EvidenceGate(), (ticker, date) -> Optional.empty(),
                guidance, CLOCK);

        ObjectiveReviewResponse response = service.review("NVDA");

        assertThat(response.assessments())
                .filteredOn(item -> item.area() == DecisionArea.EXPECTATION_VALUATION)
                .singleElement()
                .satisfies(item -> {
                    assertThat(item.status()).isEqualTo(AssessmentStatus.PARTIAL);
                    assertThat(item.limitations()).contains("상향·유지·하향 판정이 아닙니다.");
                });
        assertThat(response.evidencePacket().facts())
                .filteredOn(item -> item.id().equals("EXPECTATION.GUIDANCE.binding-1"))
                .singleElement()
                .satisfies(item -> {
                    assertThat(item.value()).isEqualTo("100–110 USD");
                    assertThat(item.source()).isEqualTo("SEC_8K_EXHIBIT");
                    assertThat(item.requiredForDecision()).isFalse();
                });
        assertThat(response.directionPrediction()).isFalse();
        assertThat(response.operationalActionRatio()).isZero();
    }

    @Test
    void hidesGuidanceOlderThanTheLockedMaximumAge() {
        HerdObservationService observations = mock(HerdObservationService.class);
        when(observations.getLatest("NVDA")).thenReturn(available());
        PitGuidanceEvidenceProvider guidance = (ticker, date) -> List.of(
                new GuidanceEvidenceFactSnapshot(
                        "old", "NVDA", "0001045810", "0001",
                        OffsetDateTime.parse("2024-01-01T12:00:00Z"),
                        "https://www.sec.gov/example", "sourcehash", "HTML_TABLE",
                        "REVENUE", "FY2024", "GAAP", "NOT_APPLICABLE", "USD",
                        BigDecimal.ONE, BigDecimal.TEN, new BigDecimal("5.5"), "v"));
        ObjectiveEvidenceService service = new ObjectiveEvidenceService(
                observations, new EvidenceGate(), (ticker, date) -> Optional.empty(),
                guidance, CLOCK);

        ObjectiveReviewResponse response = service.review("NVDA");

        assertThat(response.assessments())
                .filteredOn(item -> item.area() == DecisionArea.EXPECTATION_VALUATION)
                .singleElement()
                .extracting(DecisionAreaAssessment::status)
                .isEqualTo(AssessmentStatus.NO_VIEW);
        assertThat(response.dataGate().open()).isTrue();
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
