package com.herdsignal.service.decision;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.domain.OperatingReviewSnapshot;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.OperatingReviewSnapshotRepository;
import com.herdsignal.service.CurrentUserService;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class OperatingReviewSnapshotServiceTest {

    @Test
    void recordsHashedImmutablePayloadWithoutInventingPrice() {
        LongTermOperatingReviewService reviewService = mock(LongTermOperatingReviewService.class);
        CurrentUserService currentUser = mock(CurrentUserService.class);
        OperatingReviewSnapshotRepository repository = mock(OperatingReviewSnapshotRepository.class);
        DailyPriceRepository prices = mock(DailyPriceRepository.class);
        PersonalOperatingReviewResponse review = review();
        when(reviewService.review("NVDA")).thenReturn(review);
        when(currentUser.requireUserId()).thenReturn("user-1");
        when(prices.findTopByTickerAndClosePriceIsNotNullOrderByPriceDateDesc("NVDA"))
                .thenReturn(Optional.empty());
        when(repository.save(any())).thenAnswer(invocation -> withId(invocation.getArgument(0)));

        OperatingReviewSnapshotResponse result = new OperatingReviewSnapshotService(
                reviewService, currentUser, repository, prices,
                new ObjectMapper().findAndRegisterModules(),
                Clock.fixed(Instant.parse("2026-08-03T12:00:00Z"), ZoneOffset.UTC))
                .record("NVDA");

        assertThat(result.id()).isEqualTo(1L);
        assertThat(result.payloadSha256()).hasSize(64);
        assertThat(result.decisionCode()).isEqualTo("OBSERVE");
        assertThat(result.observationDate()).isEqualTo(LocalDate.of(2026, 8, 1));
        assertThat(result.referencePrice()).isNull();
        assertThat(result.outcomes()).allMatch(outcome -> "UNAVAILABLE".equals(outcome.status()));
    }

    @Test
    void distinguishesFutureHorizonFromMaturedMissingPrice() {
        LongTermOperatingReviewService reviewService = mock(LongTermOperatingReviewService.class);
        CurrentUserService currentUser = mock(CurrentUserService.class);
        OperatingReviewSnapshotRepository repository = mock(OperatingReviewSnapshotRepository.class);
        DailyPriceRepository prices = mock(DailyPriceRepository.class);
        when(currentUser.requireUserId()).thenReturn("user-1");
        OperatingReviewSnapshot snapshot = OperatingReviewSnapshot.builder()
                .id(2L).userId("user-1").ticker("NVDA")
                .reviewedAt(java.time.LocalDateTime.of(2026, 1, 2, 12, 0))
                .observationDate(LocalDate.of(2026, 1, 2))
                .referencePriceDate(LocalDate.of(2026, 1, 2))
                .referencePrice(new BigDecimal("100"))
                .decisionCode("OBSERVE").actionAuthorized(false).actionRatio(BigDecimal.ZERO)
                .evidenceSchemaVersion("LONG_TERM_EVIDENCE_PACKET_V1")
                .decisionModelVersion("LONG_TERM_OPERATING_V1")
                .payloadJson("{}").payloadSha256("a".repeat(64)).build();
        when(repository.findByUserIdAndTickerOrderByReviewedAtDesc("user-1", "NVDA"))
                .thenReturn(List.of(snapshot));
        when(prices.findLatestPriceDate()).thenReturn(Optional.of(LocalDate.of(2026, 2, 15)));

        OperatingReviewSnapshotResponse result = new OperatingReviewSnapshotService(
                reviewService, currentUser, repository, prices,
                new ObjectMapper().findAndRegisterModules(),
                Clock.fixed(Instant.parse("2026-02-15T12:00:00Z"), ZoneOffset.UTC))
                .history("nvda").get(0);

        assertThat(result.outcomes())
                .extracting(OperatingReviewOutcome::status)
                .containsExactly("UNAVAILABLE", "PENDING", "PENDING");
        assertThat(result.outcomes().get(0).targetDate())
                .isEqualTo(LocalDate.of(2026, 2, 2));
        assertThat(result.outcomes()).allMatch(outcome -> outcome.policyDifferencePct() == null);
    }

    private OperatingReviewSnapshot withId(OperatingReviewSnapshot row) {
        return OperatingReviewSnapshot.builder()
                .id(1L).userId(row.getUserId()).ticker(row.getTicker())
                .reviewedAt(row.getReviewedAt()).observationDate(row.getObservationDate())
                .referencePriceDate(row.getReferencePriceDate()).referencePrice(row.getReferencePrice())
                .decisionCode(row.getDecisionCode()).actionAuthorized(row.isActionAuthorized())
                .actionRatio(row.getActionRatio()).evidenceSchemaVersion(row.getEvidenceSchemaVersion())
                .decisionModelVersion(row.getDecisionModelVersion()).payloadJson(row.getPayloadJson())
                .payloadSha256(row.getPayloadSha256()).build();
    }

    private PersonalOperatingReviewResponse review() {
        EvidencePacket packet = new EvidencePacket(
                EvidencePacket.SCHEMA_VERSION, "NVDA", "UNCLASSIFIED_US_LISTED",
                OffsetDateTime.parse("2026-08-03T12:00:00Z"), List.of(
                        new EvidenceFact(
                                "OBS.STATE_SCORE", DecisionArea.CHART_CROWD, "HERD 상태 점수", "72",
                                LocalDate.of(2026, 8, 1), OffsetDateTime.parse("2026-08-02T02:00:00Z"),
                                "HERD_OBSERVATION", "HERD_STATE_S1", "UNCLASSIFIED_US_LISTED",
                                EvidenceQuality.AVAILABLE, true, false, true, 10)
                ));
        ObjectiveReviewResponse objective = new ObjectiveReviewResponse(
                "AVAILABLE", "NVDA", packet,
                new EvidenceGateResult(EvidenceGateResult.Status.OPEN, List.of()),
                List.of(), false, "OBSERVE", 0.0);
        DecisionSynthesis synthesis = new DecisionSynthesis(
                OperatingDecisionCode.OBSERVE, "상태 관찰", List.of(), List.of(),
                false, "OBSERVE", 0.0);
        return new PersonalOperatingReviewResponse(
                "OBSERVE", "NVDA", objective,
                new OperatingMandate("EXISTING_HOLDER", "BALANCED", 10, 6,
                        new BigDecimal("0.15"), new BigDecimal("0.70"),
                        5, 30, false, BigDecimal.ZERO),
                new PortfolioFitAssessment(AssessmentStatus.NO_VIEW, false, false,
                        0, 0, 0, 0, 0, "없음", "없음"),
                new RiskVeto(true, List.of("DIRECTIONAL_EVIDENCE_NOT_ADOPTED"), "차단"),
                synthesis, false, "OBSERVE", 0.0);
    }
}
