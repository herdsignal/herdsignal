package com.herdsignal.service.decision;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class DecisionSynthesisPolicyTest {
    private final DecisionSynthesisPolicy policy = new DecisionSynthesisPolicy();

    @Test
    void blockedDataAlwaysWinsOverOtherInputs() {
        DecisionSynthesis result = policy.synthesize(
                objective(EvidenceGateResult.Status.BLOCKED, AssessmentStatus.AVAILABLE),
                portfolio(),
                new RiskVeto(false, List.of(), "없음"));

        assertThat(result.decision()).isEqualTo(OperatingDecisionCode.INSUFFICIENT_DATA);
        assertThat(result.actionAuthorized()).isFalse();
        assertThat(result.operationalActionRatio()).isZero();
    }

    @Test
    void businessDamageCannotBeOffsetByOtherAreas() {
        DecisionSynthesis result = policy.synthesize(
                objective(EvidenceGateResult.Status.OPEN, AssessmentStatus.BLOCKED),
                portfolio(),
                new RiskVeto(false, List.of(), "없음"));

        assertThat(result.decision()).isEqualTo(OperatingDecisionCode.THESIS_RISK);
        assertThat(result.actionAuthorized()).isFalse();
    }

    @Test
    void missingDirectionalEvidenceStaysObservationOnly() {
        DecisionSynthesis result = policy.synthesize(
                objective(EvidenceGateResult.Status.OPEN, AssessmentStatus.NO_VIEW),
                portfolio(),
                new RiskVeto(true, List.of("DIRECTIONAL_EVIDENCE_NOT_ADOPTED"), "차단"));

        assertThat(result.decision()).isEqualTo(OperatingDecisionCode.OBSERVE);
        assertThat(result.limitations()).contains("채택된 방향성 정보 근거가 없습니다.");
        assertThat(result.operationalActionRatio()).isZero();
    }

    private ObjectiveReviewResponse objective(
            EvidenceGateResult.Status gateStatus,
            AssessmentStatus businessStatus
    ) {
        return new ObjectiveReviewResponse(
                "TEST", "NVDA", null,
                new EvidenceGateResult(gateStatus,
                        gateStatus == EvidenceGateResult.Status.OPEN ? List.of() : List.of("STALE")),
                List.of(
                        new DecisionAreaAssessment(DecisionArea.BUSINESS_HEALTH, businessStatus,
                                "기업", List.of("BUSINESS.X"), List.of()),
                        new DecisionAreaAssessment(DecisionArea.EXPECTATION_VALUATION,
                                AssessmentStatus.NO_VIEW, "기대", List.of(), List.of()),
                        new DecisionAreaAssessment(DecisionArea.INFORMATION_CHANGE,
                                AssessmentStatus.NO_VIEW, "정보", List.of(), List.of())
                ), false, "OBSERVE", 0.0);
    }

    private PortfolioFitAssessment portfolio() {
        return new PortfolioFitAssessment(
                AssessmentStatus.AVAILABLE, true, true, 0.2, 0.7, 0.7, "확인", "제한");
    }
}
