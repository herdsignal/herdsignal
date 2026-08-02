package com.herdsignal.service.decision;

/** 객관적 근거에 사용자 운용 조건과 실제 포트폴리오 맥락을 덧붙인 응답. */
public record PersonalOperatingReviewResponse(
        String status,
        String ticker,
        ObjectiveReviewResponse objective,
        OperatingMandate mandate,
        PortfolioFitAssessment portfolioFit,
        RiskVeto riskVeto,
        DecisionSynthesis synthesis,
        boolean directionPrediction,
        String operationalAction,
        double operationalActionRatio
) {
}
