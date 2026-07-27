package com.herdsignal.dto;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

public record HerdEpisodeOutcome(
        LocalDate enteredOn,
        LocalDate marketSession,
        String herdStage,
        BigDecimal entryScore,
        BigDecimal entryPrice,
        List<HerdEpisodeHorizonOutcome> horizons
) {
}
