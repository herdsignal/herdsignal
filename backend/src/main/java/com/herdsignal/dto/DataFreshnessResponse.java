package com.herdsignal.dto;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

public record DataFreshnessResponse(
        String status,
        String message,
        LocalDate latestPriceDate,
        LocalDate latestScoreDate,
        Integer priceBusinessDaysOld,
        Integer scoreBusinessDaysOld,
        SchedulerRunSummary latestRun
) {
    public record SchedulerRunSummary(
            String status,
            String triggerType,
            LocalDateTime startedAt,
            LocalDateTime finishedAt,
            int totalCount,
            int successCount,
            int failedCount,
            List<String> failedTickers,
            String errorMessage
    ) {}
}
