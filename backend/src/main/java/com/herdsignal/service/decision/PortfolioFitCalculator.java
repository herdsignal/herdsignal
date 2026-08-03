package com.herdsignal.service.decision;

import com.herdsignal.service.PortfolioActionContext;

/** 확인된 계좌 비중만 계산하고 개별 종목 목표 비중은 추정하지 않는다. */
final class PortfolioFitCalculator {

    PortfolioFitAssessment assess(PortfolioActionContext context) {
        if (context == null || !context.available()) {
            return new PortfolioFitAssessment(
                    AssessmentStatus.NO_VIEW,
                    false,
                    false,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    "포트폴리오 비중 없음",
                    "보유 수량·시세·현금이 모두 확인돼야 개인 비중을 계산합니다.");
        }
        boolean held = context.currentTickerWeight() > 0.0;
        double cashRatio = Math.max(0.0, 1.0 - context.currentEquityRatio());
        double equityTargetGap = context.currentEquityRatio() - context.targetEquityRatio();
        return new PortfolioFitAssessment(
                AssessmentStatus.AVAILABLE,
                true,
                held,
                context.currentTickerWeight(),
                context.currentEquityRatio(),
                cashRatio,
                context.targetEquityRatio(),
                equityTargetGap,
                held ? "현재 보유 비중 확인" : "현재 미보유",
                "개별 종목 목표 비중이 없으므로 과대·과소 비중을 추정하지 않습니다.");
    }
}
