package com.herdsignal.service;

import java.util.List;

/** 최근 같은 방향의 실제 행동이 있으면 반복 행동을 차단한다. */
final class ActionCooldownPolicy {
    private static final double SCATTER_UPPER = 40.0;
    private static final double DRIFT_LOWER = 60.0;

    ActionDecisionService.CooldownAdjustment apply(
            ActionDecisionService.RegimeDecision regime,
            ActionCooldownContext context,
            double herdScore
    ) {
        boolean buySide = herdScore <= SCATTER_UPPER;
        boolean sellSide = herdScore >= DRIFT_LOWER || regime.code().startsWith("RISK_REBALANCE");
        if (regime.ratio() == 0.0 || (!buySide && !sellSide)) {
            return new ActionDecisionService.CooldownAdjustment(
                    regime, ActionCooldownContext.Cooldown.none(), null, List.of());
        }
        ActionCooldownContext.Cooldown cooldown = context.forBuySide(buySide);
        if (!cooldown.active()) {
            return new ActionDecisionService.CooldownAdjustment(regime, cooldown, null, List.of());
        }

        String direction = buySide ? "매수" : "비중 축소";
        ActionDecisionService.RegimeDecision blocked = new ActionDecisionService.RegimeDecision(
                regime.code() + "_COOLDOWN", "최근 " + direction + " 후 대기",
                regime.regimeLabel(), 0.0,
                regime.reason() + " 동일 방향의 최근 실제 행동으로 쿨다운을 적용합니다.");
        String reason = String.format("최근 %s %s · 쿨다운 %d거래일 남음",
                direction, cooldown.lastActionDate(), cooldown.remainingTradingDays());
        return new ActionDecisionService.CooldownAdjustment(blocked, cooldown, reason,
                List.of("같은 방향의 반복 행동을 막기 위해 쿨다운 종료 전까지 비율을 0%로 제한합니다."));
    }
}
