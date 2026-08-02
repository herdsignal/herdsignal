package com.herdsignal.service.decision;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

public record OperatingReviewSnapshotResponse(
        long id,
        String ticker,
        LocalDateTime reviewedAt,
        LocalDate observationDate,
        LocalDate referencePriceDate,
        BigDecimal referencePrice,
        String decisionCode,
        boolean actionAuthorized,
        BigDecimal actionRatio,
        String evidenceSchemaVersion,
        String decisionModelVersion,
        String payloadSha256,
        List<OperatingReviewOutcome> outcomes
) {
    public OperatingReviewSnapshotResponse {
        outcomes = outcomes == null ? List.of() : List.copyOf(outcomes);
    }
}
