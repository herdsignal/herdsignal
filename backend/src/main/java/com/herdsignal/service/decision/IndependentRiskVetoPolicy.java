package com.herdsignal.service.decision;

import java.util.ArrayList;
import java.util.List;

/** 다른 영역의 점수로 상쇄할 수 없는 운영 차단 조건만 판정한다. */
final class IndependentRiskVetoPolicy {

    RiskVeto evaluate(
            ObjectiveReviewResponse objective,
            PortfolioFitAssessment portfolioFit
    ) {
        List<String> codes = new ArrayList<>();
        if (!objective.dataGate().open()) {
            codes.add("DATA_GATE_BLOCKED");
        }
        if (hasStatus(objective, DecisionArea.BUSINESS_HEALTH, AssessmentStatus.NO_VIEW)) {
            codes.add("BUSINESS_HEALTH_NOT_CONNECTED");
        }
        if (hasStatus(objective, DecisionArea.INFORMATION_CHANGE, AssessmentStatus.NO_VIEW)
                || !objective.directionPrediction()) {
            codes.add("DIRECTIONAL_EVIDENCE_NOT_ADOPTED");
        }
        if (portfolioFit == null || !portfolioFit.portfolioAvailable()) {
            codes.add("PORTFOLIO_CONTEXT_NOT_CONNECTED");
        }
        return new RiskVeto(
                !codes.isEmpty(),
                codes.stream().distinct().toList(),
                codes.isEmpty() ? "독립 차단 조건 없음" : "운영 행동 권한 없음");
    }

    private boolean hasStatus(
            ObjectiveReviewResponse objective,
            DecisionArea area,
            AssessmentStatus status
    ) {
        return objective.assessments().stream()
                .anyMatch(item -> item.area() == area && item.status() == status);
    }
}
