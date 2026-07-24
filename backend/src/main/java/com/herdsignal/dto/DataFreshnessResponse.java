package com.herdsignal.dto;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;

public record DataFreshnessResponse(
        String status,
        String message,
        LocalDate latestPriceDate,
        LocalDate latestScoreDate,
        Integer priceBusinessDaysOld,
        Integer scoreBusinessDaysOld,
        int expectedTickerCount,
        int freshPriceTickerCount,
        int freshScoreTickerCount,
        int missingPriceTickerCount,
        int missingScoreTickerCount,
        SchedulerRunSummary latestRun
) {
    public record SchedulerRunSummary(
            String status,
            String triggerType,
            OffsetDateTime startedAt,
            OffsetDateTime finishedAt,
            int totalCount,
            int successCount,
            int failedCount,
            List<String> failedTickers,
            String errorMessage
    ) {}
}
