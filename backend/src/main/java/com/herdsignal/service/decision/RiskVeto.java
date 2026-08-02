package com.herdsignal.service.decision;

import java.util.List;

/** 다른 영역의 점수로 상쇄할 수 없는 행동 차단 결과. */
public record RiskVeto(
        boolean actionBlocked,
        List<String> codes,
        String headline
) {
    public RiskVeto {
        codes = codes == null ? List.of() : List.copyOf(codes);
    }
}
