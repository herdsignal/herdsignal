package com.herdsignal.service;

import java.math.BigDecimal;
import java.math.RoundingMode;

/** 데이터 신뢰도와 신호 생명주기로 행동 비율만 조정한다. */
final class ActionRatioAdjustmentPolicy {
    private static final double SCATTER_UPPER = 40.0;
    private static final double DRIFT_LOWER = 60.0;

    ActionDecisionService.RegimeDecision applyConfidence(
            ActionDecisionService.RegimeDecision regime,
            int dataQuality,
            HerdMomentumCalculator.Result momentum
    ) {
        if (regime.ratio() == 0.0) return regime;
        double quality = dataQuality >= 85 ? 1.0 : dataQuality >= 65 ? 0.85
                : dataQuality >= 50 ? 0.65 : 0.40;
        double history = momentum.observations() >= 20 ? 1.0
                : momentum.observations() >= 5 ? 0.85 : 0.65;
        double ratio = rounded(regime.ratio() * quality * history);
        return new ActionDecisionService.RegimeDecision(
                regime.code(), regime.label(), regime.regimeLabel(), ratio,
                regime.reason() + String.format(" 신뢰도 보정 %.0f%%를 적용합니다.", quality * history * 100));
    }

    ActionDecisionService.RegimeDecision applyLifecycle(
            ActionDecisionService.RegimeDecision regime,
            HerdLifecycleClassifier.Result lifecycle,
            double herdScore
    ) {
        if (regime.ratio() == 0.0) return regime;
        double ratio = rounded(regime.ratio() * lifecycle.ratioMultiplier());
        if (lifecycle.signalDays() <= 5 && ratio > 0.0) {
            return new ActionDecisionService.RegimeDecision(
                    regime.code() + "_FRESH", label(regime.label(), herdScore, false),
                    regime.regimeLabel(), ratio,
                    regime.reason() + " 단, 신호 초입이라 첫 행동 비율을 낮춥니다.");
        }
        if (lifecycle.signalDays() > 45 && ratio > 0.0) {
            return new ActionDecisionService.RegimeDecision(
                    regime.code() + "_EXTENDED", label(regime.label(), herdScore, true),
                    regime.regimeLabel(), ratio,
                    regime.reason() + " 다만 오래 지속된 신호라 추격 비중을 제한합니다.");
        }
        return new ActionDecisionService.RegimeDecision(
                regime.code(), regime.label(), regime.regimeLabel(), ratio, regime.reason());
    }

    private String label(String original, double herdScore, boolean extended) {
        if (extended && herdScore <= SCATTER_UPPER) return "추격매수 보류";
        if (extended && herdScore >= DRIFT_LOWER) return "분할 익절 유지";
        if (!extended && (herdScore <= SCATTER_UPPER || herdScore >= DRIFT_LOWER)) {
            return original.replace("적극 ", "").replace("후보", "확인");
        }
        return original;
    }

    private double rounded(double value) {
        return BigDecimal.valueOf(value).setScale(2, RoundingMode.HALF_UP).doubleValue();
    }
}
