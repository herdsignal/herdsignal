package com.herdsignal.service.decision;

import java.util.List;

/** 기대·밸류 영역에서 확인된 사실과 의도적으로 비워 둔 범위를 함께 반환한다. */
record ExpectationValuationEvidenceBundle(
        List<EvidenceFact> facts,
        DecisionAreaAssessment assessment
) {
    ExpectationValuationEvidenceBundle {
        facts = facts == null ? List.of() : List.copyOf(facts);
    }
}
