package com.herdsignal.dto;

import java.math.BigDecimal;

public record HerdEpisodeHorizonSummary(
        int weeks,
        int completedCount,
        BigDecimal medianReturnPct,
        BigDecimal positiveRatePct,
        BigDecimal medianMaxDrawdownPct
) {
}
