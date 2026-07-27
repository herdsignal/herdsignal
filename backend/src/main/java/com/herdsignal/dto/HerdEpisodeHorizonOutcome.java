package com.herdsignal.dto;

import java.math.BigDecimal;
import java.time.LocalDate;

public record HerdEpisodeHorizonOutcome(
        int weeks,
        String status,
        LocalDate endSession,
        BigDecimal returnPct,
        BigDecimal maxDrawdownPct
) {
}
