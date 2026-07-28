package com.herdsignal.dto;

import java.math.BigDecimal;

public record HistoricalS1ContextSummary(
        int horizonSessions,
        int completedEpisodes,
        BigDecimal medianReturnPct,
        BigDecimal positiveRatePct,
        BigDecimal medianMfePct,
        BigDecimal medianMaePct
) {
}
