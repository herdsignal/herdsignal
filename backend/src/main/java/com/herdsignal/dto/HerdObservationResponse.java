package com.herdsignal.dto;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;

/** v4와 분리된 HERD State S1 최신 관찰 응답. */
public record HerdObservationResponse(
        String availabilityStatus,
        String freshnessStatus,
        Integer businessSessionsOld,
        String ticker,
        String label,
        String scope,
        String claimCode,
        String schemaVersion,
        String stateModelVersion,
        String transitionModelVersion,
        LocalDate observationDate,
        LocalDate lastObservedSession,
        OffsetDateTime generatedAt,
        BigDecimal stateScore,
        String stage,
        String transition,
        String rawTransition,
        boolean transitionEvent,
        BigDecimal delta4w,
        BigDecimal delta13w,
        FamilyScores families,
        BigDecimal downsideRiskContext,
        String sectorEtf,
        BigDecimal referenceCoverageFraction,
        boolean directionPrediction,
        String operationalAction,
        BigDecimal operationalActionRatio,
        boolean survivorshipSafe
) {
    public record FamilyScores(
            BigDecimal priceExtension,
            BigDecimal trendPosition,
            BigDecimal relativePosition,
            BigDecimal participation
    ) {}
}
