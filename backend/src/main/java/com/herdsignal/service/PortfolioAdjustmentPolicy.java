package com.herdsignal.service;

import com.herdsignal.domain.InvestorProfile;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;

/** 실제 포트폴리오 집중도와 목표 비중으로 연구 행동의 크기를 제한한다. */
final class PortfolioAdjustmentPolicy {
    private static final double SCATTER_UPPER = 40.0;
    private static final double RUSH_THRESHOLD = 75.0;

    ActionDecisionService.PortfolioAdjustment adjust(
            ActionDecisionService.RegimeDecision regime,
            PortfolioActionContext context,
            InvestorProfile profile,
            double herdScore
    ) {
        if (context.available() && context.currentTickerWeight() >= 0.25) {
            ActionDecisionService.RegimeDecision riskRebalance = new ActionDecisionService.RegimeDecision(
                    "RISK_REBALANCE_CONCENTRATION",
                    "집중도 리밸런싱 후보",
                    regime.regimeLabel(),
                    0.05,
                    "현재 종목 비중이 25% 이상이라 수익률 예측과 별개로 집중 위험 축소를 검토합니다."
            );
            return new ActionDecisionService.PortfolioAdjustment(
                    riskRebalance,
                    context,
                    String.format("현재 종목 비중 %.1f%% · 위험 리밸런싱 기준 25%%",
                            context.currentTickerWeight() * 100),
                    List.of("이 축소는 HERD 익절 신호가 아니라 포트폴리오 집중 위험 관리입니다.")
            );
        }
        if (!context.available() || regime.ratio() == 0.0) {
            return new ActionDecisionService.PortfolioAdjustment(regime, context, null, List.of());
        }
        boolean buySide = herdScore <= SCATTER_UPPER;
        if (buySide && context.currentEquityRatio() >= context.targetEquityRatio() + 0.03) {
            return blocked(regime, context, "목표 주식 비중 초과",
                    String.format("현재 주식 비중 %.1f%% · 목표 %.1f%%",
                            context.currentEquityRatio() * 100, context.targetEquityRatio() * 100),
                    "전체 주식 비중이 목표 범위를 초과해 추가매수를 제한합니다.");
        }
        if (buySide && context.currentTickerWeight() >= 0.15) {
            double ratio = BigDecimal.valueOf(regime.ratio() * 0.5)
                    .setScale(2, RoundingMode.HALF_UP).doubleValue();
            ActionDecisionService.RegimeDecision reduced = new ActionDecisionService.RegimeDecision(
                    regime.code() + "_CONCENTRATION", regime.label(), regime.regimeLabel(), ratio,
                    regime.reason() + " 현재 종목 집중도를 반영해 행동 비율을 절반으로 줄입니다.");
            return new ActionDecisionService.PortfolioAdjustment(reduced, context,
                    String.format("현재 종목 비중 %.1f%% · 집중도 보정 50%%", context.currentTickerWeight() * 100),
                    List.of("종목 비중이 15% 이상이라 추가매수 강도를 낮춥니다."));
        }

        String strategy = profile == null ? "EXISTING_HOLDER" : profile.getStrategy();
        if (!buySide && "TARGET_REBALANCE".equals(strategy) && herdScore < RUSH_THRESHOLD
                && context.currentEquityRatio() <= context.targetEquityRatio() - 0.03) {
            return blocked(regime, context, "목표 비중 회복 우선",
                    String.format("현재 주식 비중 %.1f%% · 목표 %.1f%%",
                            context.currentEquityRatio() * 100, context.targetEquityRatio() * 100),
                    "주식 비중이 목표보다 낮아 Drift 단계의 추가 축소를 보류합니다.");
        }
        return new ActionDecisionService.PortfolioAdjustment(regime, context,
                String.format("현재 종목 %.1f%% · 주식 %.1f%% / 목표 %.1f%%",
                        context.currentTickerWeight() * 100, context.currentEquityRatio() * 100,
                        context.targetEquityRatio() * 100), List.of());
    }

    private ActionDecisionService.PortfolioAdjustment blocked(
            ActionDecisionService.RegimeDecision regime, PortfolioActionContext context,
            String label, String reason, String warning
    ) {
        ActionDecisionService.RegimeDecision blocked = new ActionDecisionService.RegimeDecision(
                regime.code() + "_PORTFOLIO_LIMIT", label, regime.regimeLabel(), 0.0,
                regime.reason() + " 실제 포트폴리오 비중 제한을 적용합니다.");
        return new ActionDecisionService.PortfolioAdjustment(blocked, context, reason, List.of(warning));
    }
}
