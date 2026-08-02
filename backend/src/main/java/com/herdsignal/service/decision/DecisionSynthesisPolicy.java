package com.herdsignal.service.decision;

import org.springframework.stereotype.Component;

import java.util.LinkedHashSet;
import java.util.List;

/** 결과를 본 뒤 바꾸는 가중치 없이, 사전에 정한 우선순위로만 판단한다. */
@Component
public class DecisionSynthesisPolicy {

    public DecisionSynthesis synthesize(
            ObjectiveReviewResponse objective,
            PortfolioFitAssessment portfolioFit,
            RiskVeto veto
    ) {
        if (!objective.dataGate().open()) {
            return result(
                    OperatingDecisionCode.INSUFFICIENT_DATA,
                    "필수 관찰 데이터 확인 필요",
                    List.of(),
                    objective.dataGate().reasons(),
                    false
            );
        }
        if (veto.codes().contains("INDEPENDENT_RISK_HARD_STOP")) {
            return result(
                    OperatingDecisionCode.RISK_VETO,
                    "독립 위험 조건으로 행동 차단",
                    availableEvidence(objective),
                    veto.codes(),
                    false
            );
        }
        if (assessmentStatus(objective, DecisionArea.BUSINESS_HEALTH) == AssessmentStatus.BLOCKED) {
            return result(
                    OperatingDecisionCode.THESIS_RISK,
                    "기업 투자 근거 재검토 필요",
                    evidenceFor(objective, DecisionArea.BUSINESS_HEALTH),
                    List.of("기업 훼손 확인은 다른 영역의 강한 점수로 상쇄하지 않습니다."),
                    false
            );
        }

        LinkedHashSet<String> limitations = new LinkedHashSet<>();
        if (assessmentStatus(objective, DecisionArea.BUSINESS_HEALTH) != AssessmentStatus.AVAILABLE) {
            limitations.add("PIT 기업 체력 근거가 연결되지 않았습니다.");
        }
        if (assessmentStatus(objective, DecisionArea.EXPECTATION_VALUATION) != AssessmentStatus.AVAILABLE) {
            limitations.add("PIT 기대·가격 근거가 연결되지 않았습니다.");
        }
        if (assessmentStatus(objective, DecisionArea.INFORMATION_CHANGE) != AssessmentStatus.AVAILABLE) {
            limitations.add("채택된 방향성 정보 근거가 없습니다.");
        }
        if (!portfolioFit.portfolioAvailable()) {
            limitations.add("개인 포트폴리오 비중을 확인할 수 없습니다.");
        }
        if (veto.actionBlocked()) {
            limitations.addAll(veto.codes());
        }
        return result(
                OperatingDecisionCode.OBSERVE,
                "상태 관찰",
                availableEvidence(objective),
                List.copyOf(limitations),
                false
        );
    }

    private DecisionSynthesis result(
            OperatingDecisionCode code,
            String headline,
            List<String> evidenceRefs,
            List<String> limitations,
            boolean authorized
    ) {
        return new DecisionSynthesis(
                code, headline, evidenceRefs, limitations, authorized, "OBSERVE", 0.0);
    }

    private AssessmentStatus assessmentStatus(ObjectiveReviewResponse objective, DecisionArea area) {
        return objective.assessments().stream()
                .filter(item -> item.area() == area)
                .map(DecisionAreaAssessment::status)
                .findFirst()
                .orElse(AssessmentStatus.NO_VIEW);
    }

    private List<String> availableEvidence(ObjectiveReviewResponse objective) {
        if (objective.evidencePacket() == null) {
            return List.of();
        }
        return objective.evidencePacket().facts().stream()
                .filter(fact -> fact.quality() == EvidenceQuality.AVAILABLE)
                .map(EvidenceFact::id)
                .distinct()
                .toList();
    }

    private List<String> evidenceFor(ObjectiveReviewResponse objective, DecisionArea area) {
        return objective.assessments().stream()
                .filter(item -> item.area() == area)
                .flatMap(item -> item.evidenceIds().stream())
                .distinct()
                .toList();
    }
}
