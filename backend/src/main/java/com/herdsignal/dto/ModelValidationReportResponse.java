package com.herdsignal.dto;

import java.util.List;

/** HERD Lab에 공개할 검증 리포트의 요약 응답. */
public record ModelValidationReportResponse(
        String generatedAt,
        String modelVersion,
        String universeVersion,
        ValidationRun validationRun,
        PerformanceSummary fullPeriod,
        PerformanceSummary walkForward,
        ParameterStability parameterStability,
        Overfitting overfitting,
        AdoptionGate adoptionGate,
        boolean scoreParityPassed,
        String survivorshipStatus,
        List<TickerResult> tickers
) {
    public record ValidationRun(
            String status,
            int requestedTickers,
            int completedTickers,
            double coverage,
            int embargoDays
    ) {}

    public record PerformanceSummary(
            int samples,
            Double captureMedian,
            Double mddImprovementMedian,
            Double improvementRate,
            String worstTicker
    ) {}

    public record ParameterStability(
            int samples,
            Double sameParameterRate,
            boolean singleParameterSpike,
            String recommendation
    ) {}

    public record Overfitting(
            int parametersTested,
            Double pbo,
            String pboStatus,
            Double deflatedSharpeProbability,
            String deflatedSharpeStatus
    ) {}

    public record AdoptionGate(
            String policyVersion,
            String status,
            boolean eligibleForHumanReview,
            boolean automaticProductionPromotion,
            List<String> failedCriteria
    ) {}

    public record TickerResult(
            String ticker,
            String start,
            String end,
            Double buyHoldReturn,
            Double actionReturn,
            Double capture,
            Double mddImprovement,
            int actions
    ) {}
}
