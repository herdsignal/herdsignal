package com.herdsignal.service.decision;

import java.util.List;

/** SEC PIT 기업 사실과 그 사실만으로 허용되는 설명 범위를 함께 반환한다. */
record BusinessHealthEvidenceBundle(
        List<EvidenceFact> facts,
        DecisionAreaAssessment assessment
) {
    BusinessHealthEvidenceBundle {
        facts = facts == null ? List.of() : List.copyOf(facts);
    }
}
