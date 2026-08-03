package com.herdsignal.service.decision;

/** 사실로 확인 가능한 포트폴리오 비중만 제공하고 목표 종목 비중은 추정하지 않는다. */
public record PortfolioFitAssessment(
        AssessmentStatus status,
        boolean portfolioAvailable,
        boolean held,
        double currentTickerWeight,
        double currentEquityRatio,
        double currentCashRatio,
        double targetEquityRatio,
        double equityTargetGap,
        String headline,
        String limitation
) {
}
