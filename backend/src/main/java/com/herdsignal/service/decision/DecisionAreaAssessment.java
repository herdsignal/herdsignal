package com.herdsignal.service.decision;

import java.util.List;

/** 영역별 구조화 결과. 모든 설명은 evidenceIds로 역추적할 수 있어야 한다. */
public record DecisionAreaAssessment(
        DecisionArea area,
        AssessmentStatus status,
        String headline,
        List<String> evidenceIds,
        List<String> limitations
) {
    public DecisionAreaAssessment {
        evidenceIds = evidenceIds == null ? List.of() : List.copyOf(evidenceIds);
        limitations = limitations == null ? List.of() : List.copyOf(limitations);
    }
}
