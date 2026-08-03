package com.herdsignal.service.decision;

import java.util.List;

/** 비가격 사건 원천별 운영 연결 상태를 방향 해석 없이 반환한다. */
record InformationChangeEvidenceBundle(
        List<EvidenceFact> facts,
        DecisionAreaAssessment assessment
) {
    InformationChangeEvidenceBundle {
        facts = facts == null ? List.of() : List.copyOf(facts);
    }
}
