package com.herdsignal.dto;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;

public record EvidenceReviewResponse(
        String status,
        String scope,
        String ticker,
        LocalDate asOf,
        String model,
        List<Lens> lenses,
        String summary,
        List<String> disagreements,
        List<String> factsToVerify,
        List<EvidenceFact> evidence,
        boolean directionPrediction,
        String operationalAction,
        BigDecimal operationalActionRatio,
        String notice
) {
    public record Lens(
            String code,
            String stance,
            String summary,
            List<String> evidenceIds,
            List<String> missingEvidence
    ) {}

    public record EvidenceFact(
            String id,
            String area,
            String label,
            String value,
            LocalDate asOf,
            OffsetDateTime observedAt,
            String source,
            String sourceVersion,
            String quality
    ) {}
}
