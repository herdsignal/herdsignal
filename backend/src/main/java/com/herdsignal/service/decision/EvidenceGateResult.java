package com.herdsignal.service.decision;

import java.util.List;

/** 데이터 gate 판정. 차단 이유는 사용자 설명과 감사 기록에 그대로 보존한다. */
public record EvidenceGateResult(
        Status status,
        List<String> reasons
) {
    public enum Status { OPEN, BLOCKED }

    public EvidenceGateResult {
        reasons = reasons == null ? List.of() : List.copyOf(reasons);
    }

    public boolean open() {
        return status == Status.OPEN;
    }
}
