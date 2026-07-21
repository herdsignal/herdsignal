package com.herdsignal.service;

/** 예측형 익절과 포트폴리오 위험 리밸런싱의 행동 권한을 분리한다. */
final class ActionAuthorityPolicy {
    private static final double DRIFT_LOWER = 60.0;

    ActionDecisionService.RegimeDecision apply(
            ActionDecisionService.RegimeDecision regime,
            double herdScore
    ) {
        if (regime.ratio() == 0.0 || herdScore < DRIFT_LOWER || isRiskRebalance(regime)) {
            return regime;
        }
        return new ActionDecisionService.RegimeDecision(
                "PROFIT_TAKE_EVIDENCE_BLOCKED",
                "익절 근거 미채택",
                regime.regimeLabel(),
                0.0,
                regime.reason() + " 가격·군중 상태 기반 익절은 독립 OOS 근거가 없어 차단합니다."
        );
    }

    boolean isRiskRebalance(ActionDecisionService.RegimeDecision regime) {
        return regime.code().startsWith("RISK_REBALANCE");
    }
}
