package com.herdsignal.service.decision;

import java.util.List;

/** 규칙 기반 종합 판단. 근거 ID 밖의 정보로 설명을 확장하지 않는다. */
public record DecisionSynthesis(
        OperatingDecisionCode decision,
        String headline,
        List<String> evidenceRefs,
        List<String> limitations,
        boolean actionAuthorized,
        String operationalAction,
        double operationalActionRatio
) {
    public DecisionSynthesis {
        evidenceRefs = evidenceRefs == null ? List.of() : List.copyOf(evidenceRefs);
        limitations = limitations == null ? List.of() : List.copyOf(limitations);
    }
}
