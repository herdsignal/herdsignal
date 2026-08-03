package com.herdsignal.service;

import com.herdsignal.dto.EvidenceReviewResponse;
import com.herdsignal.service.decision.DecisionArea;
import com.herdsignal.service.decision.DecisionAreaAssessment;
import com.herdsignal.service.decision.EvidenceFact;
import com.herdsignal.service.decision.EvidenceGateResult;
import com.herdsignal.service.decision.EvidencePacket;
import com.herdsignal.service.decision.EvidenceQuality;
import com.herdsignal.service.decision.ObjectiveEvidenceService;
import com.herdsignal.service.decision.ObjectiveReviewResponse;
import com.herdsignal.service.decision.AssessmentStatus;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class EvidenceReviewServiceTest {
    private ObjectiveEvidenceService objectiveEvidenceService;
    private EvidenceReviewGateway gateway;
    private CurrentUserService currentUserService;
    private EvidenceReviewService service;

    @BeforeEach
    void setUp() {
        objectiveEvidenceService = mock(ObjectiveEvidenceService.class);
        gateway = mock(EvidenceReviewGateway.class);
        currentUserService = mock(CurrentUserService.class);
        service = new EvidenceReviewService(objectiveEvidenceService, gateway, currentUserService);
        when(objectiveEvidenceService.review("NVDA")).thenReturn(objective(true));
        when(gateway.model()).thenReturn("test-model");
        when(currentUserService.requireUserId()).thenReturn("local");
    }

    @Test
    void disabledGatewayReturnsFactsButNeverAction() {
        when(gateway.isEnabled()).thenReturn(false);

        EvidenceReviewResponse response = service.review("NVDA");

        assertThat(response.status()).isEqualTo("DISABLED");
        assertThat(response.evidence()).extracting(EvidenceReviewResponse.EvidenceFact::id)
                .contains("OBS.STATE_SCORE", "BUSINESS.PIT.REVENUE_YOY");
        assertThat(response.evidence()).extracting(EvidenceReviewResponse.EvidenceFact::area)
                .contains("CHART_CROWD", "BUSINESS_HEALTH");
        assertThat(response.directionPrediction()).isFalse();
        assertThat(response.operationalAction()).isEqualTo("HOLD");
        assertThat(response.operationalActionRatio()).isEqualByComparingTo(BigDecimal.ZERO);
    }

    @Test
    void validGroundedDraftIsReturned() {
        when(gateway.isEnabled()).thenReturn(true);
        when(gateway.review(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any()))
                .thenReturn(validDraft());

        EvidenceReviewResponse response = service.review("NVDA");

        assertThat(response.status()).isEqualTo("AVAILABLE");
        assertThat(response.lenses()).hasSize(6);
        assertThat(response.summary()).isEqualTo("상태 근거만 요약");
    }

    @Test
    void evidenceFromAnotherAreaFailsClosed() {
        when(gateway.isEnabled()).thenReturn(true);
        EvidenceReviewGateway.Draft draft = validDraft();
        List<EvidenceReviewResponse.Lens> crossed = draft.lenses().stream()
                .map(lens -> "BUSINESS_HEALTH".equals(lens.code())
                        ? lens("BUSINESS_HEALTH", "OBS.STATE_SCORE") : lens)
                .toList();
        when(gateway.review(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any()))
                .thenReturn(new EvidenceReviewGateway.Draft(
                        crossed, draft.summary(), List.of(), List.of(), false, "HOLD", 0.0));

        assertThat(service.review("NVDA").status()).isEqualTo("PROVIDER_ERROR");
    }

    @Test
    void unknownEvidenceIdFailsClosed() {
        when(gateway.isEnabled()).thenReturn(true);
        when(gateway.review(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any()))
                .thenReturn(draftWithRedTeamEvidence("NEWS.UNKNOWN"));

        assertThat(service.review("NVDA").status()).isEqualTo("PROVIDER_ERROR");
    }

    @Test
    void actionBearingDraftFailsClosed() {
        when(gateway.isEnabled()).thenReturn(true);
        EvidenceReviewGateway.Draft draft = new EvidenceReviewGateway.Draft(
                validDraft().lenses(), "매수", List.of(), List.of(),
                true, "BUY", 5.0
        );
        when(gateway.review(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any()))
                .thenReturn(draft);

        EvidenceReviewResponse response = service.review("NVDA");
        assertThat(response.status()).isEqualTo("PROVIDER_ERROR");
        assertThat(response.operationalAction()).isEqualTo("HOLD");
        assertThat(response.operationalActionRatio()).isEqualByComparingTo(BigDecimal.ZERO);
    }

    @Test
    void closedDataGateSkipsTheProvider() {
        when(objectiveEvidenceService.review("NVDA")).thenReturn(objective(false));
        when(gateway.isEnabled()).thenReturn(true);

        EvidenceReviewResponse response = service.review("NVDA");

        assertThat(response.status()).isEqualTo("INSUFFICIENT_EVIDENCE");
        org.mockito.Mockito.verifyNoInteractions(currentUserService);
    }

    private EvidenceReviewGateway.Draft validDraft() {
        List<EvidenceReviewResponse.Lens> lenses = List.of(
                lens("BUSINESS_HEALTH", "BUSINESS.PIT.REVENUE_YOY"),
                lens("EXPECTATION_VALUATION", "EXPECTATION.GUIDANCE.REVENUE"),
                lens("MARKET_SECTOR", "MARKET.SPY.RETURN_63"),
                lens("CHART_CROWD", "OBS.STATE_SCORE"),
                lens("INFORMATION_CHANGE", "INFORMATION.SEC_MATERIAL_EVENT"),
                lens("RED_TEAM", "OBS.STATE_SCORE")
        );
        return new EvidenceReviewGateway.Draft(
                lenses, "상태 근거만 요약", List.of(), List.of("기업 실적"),
                false, "HOLD", 0.0
        );
    }

    private EvidenceReviewGateway.Draft draftWithRedTeamEvidence(String evidenceId) {
        EvidenceReviewGateway.Draft valid = validDraft();
        List<EvidenceReviewResponse.Lens> lenses = valid.lenses().stream()
                .map(lens -> "RED_TEAM".equals(lens.code()) ? lens("RED_TEAM", evidenceId) : lens)
                .toList();
        return new EvidenceReviewGateway.Draft(
                lenses, valid.summary(), List.of(), List.of(), false, "HOLD", 0.0);
    }

    private EvidenceReviewResponse.Lens lens(String code, String evidenceId) {
        return new EvidenceReviewResponse.Lens(
                code, "NEUTRAL", "관찰", List.of(evidenceId), List.of()
        );
    }

    private ObjectiveReviewResponse objective(boolean gateOpen) {
        LocalDate date = LocalDate.of(2026, 7, 31);
        List<EvidenceFact> facts = List.of(
                fact("BUSINESS.PIT.REVENUE_YOY", DecisionArea.BUSINESS_HEALTH, "0.25", date),
                fact("EXPECTATION.GUIDANCE.REVENUE", DecisionArea.EXPECTATION_VALUATION, "$10B", date),
                fact("MARKET.SPY.RETURN_63", DecisionArea.MARKET_SECTOR, "0.04", date),
                fact("OBS.STATE_SCORE", DecisionArea.CHART_CROWD, "62", date),
                fact("INFORMATION.SEC_MATERIAL_EVENT", DecisionArea.INFORMATION_CHANGE, "none", date)
        );
        EvidencePacket packet = new EvidencePacket(
                EvidencePacket.SCHEMA_VERSION, "NVDA", "COMMON_STOCK",
                OffsetDateTime.parse("2026-08-01T00:00:00Z"), facts);
        EvidenceGateResult gate = new EvidenceGateResult(
                gateOpen ? EvidenceGateResult.Status.OPEN : EvidenceGateResult.Status.BLOCKED,
                gateOpen ? List.of() : List.of("STALE"));
        List<DecisionAreaAssessment> assessments = Arrays.stream(DecisionArea.values())
                .filter(area -> List.of(
                        DecisionArea.BUSINESS_HEALTH,
                        DecisionArea.EXPECTATION_VALUATION,
                        DecisionArea.MARKET_SECTOR,
                        DecisionArea.CHART_CROWD,
                        DecisionArea.INFORMATION_CHANGE).contains(area))
                .map(area -> new DecisionAreaAssessment(
                        area, AssessmentStatus.AVAILABLE, area.name(), List.of(), List.of()))
                .toList();
        return new ObjectiveReviewResponse(
                gateOpen ? "AVAILABLE" : "INSUFFICIENT_DATA", "NVDA", packet, gate,
                assessments, false, "OBSERVE", 0.0);
    }

    private EvidenceFact fact(String id, DecisionArea area, String value, LocalDate date) {
        return new EvidenceFact(
                id, area, id, value, date, OffsetDateTime.parse("2026-08-01T00:00:00Z"),
                "TEST_SOURCE", "V1", "COMMON_STOCK", EvidenceQuality.AVAILABLE,
                false, false, true, 10);
    }
}
