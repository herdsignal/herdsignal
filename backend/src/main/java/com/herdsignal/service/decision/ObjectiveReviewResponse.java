package com.herdsignal.service.decision;

import java.util.List;

/** 개인 보유정보를 넣기 전의 객관적 장기 운용 근거 응답. */
public record ObjectiveReviewResponse(
        String status,
        String ticker,
        EvidencePacket evidencePacket,
        EvidenceGateResult dataGate,
        List<DecisionAreaAssessment> assessments,
        boolean directionPrediction,
        String operationalAction,
        double operationalActionRatio
) {
    public ObjectiveReviewResponse {
        assessments = assessments == null ? List.of() : List.copyOf(assessments);
    }
}
