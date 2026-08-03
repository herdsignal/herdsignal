package com.herdsignal.service.decision;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class IndependentRiskVetoPolicyTest {
    private final IndependentRiskVetoPolicy policy = new IndependentRiskVetoPolicy();

    @Test
    void keepsMissingDirectionAndPortfolioAsSeparateBlocks() {
        ObjectiveReviewResponse objective = new ObjectiveReviewResponse(
                "AVAILABLE", "NVDA", null,
                new EvidenceGateResult(EvidenceGateResult.Status.OPEN, List.of()),
                List.of(
                        assessment(DecisionArea.BUSINESS_HEALTH, AssessmentStatus.PARTIAL),
                        assessment(DecisionArea.INFORMATION_CHANGE, AssessmentStatus.NO_VIEW)),
                false, "OBSERVE", 0.0);
        PortfolioFitAssessment unavailable = new PortfolioFitCalculator().assess(null);

        RiskVeto result = policy.evaluate(objective, unavailable);

        assertThat(result.actionBlocked()).isTrue();
        assertThat(result.codes()).containsExactly(
                "DIRECTIONAL_EVIDENCE_NOT_ADOPTED",
                "PORTFOLIO_CONTEXT_NOT_CONNECTED");
    }

    private DecisionAreaAssessment assessment(DecisionArea area, AssessmentStatus status) {
        return new DecisionAreaAssessment(area, status, "test", List.of(), List.of());
    }
}
