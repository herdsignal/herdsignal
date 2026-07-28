package com.herdsignal.dto;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;

public record DataFreshnessResponse(
        String status,
        String message,
        LocalDate latestPriceDate,
        LocalDate latestObservationDate,
        LocalDate latestScoreDate,
        Integer priceBusinessDaysOld,
        Integer observationBusinessDaysOld,
        Integer scoreBusinessDaysOld,
        int expectedTickerCount,
        int freshPriceTickerCount,
        int expectedObservationTickerCount,
        int freshObservationTickerCount,
        int missingObservationTickerCount,
        int freshScoreTickerCount,
        int missingPriceTickerCount,
        int missingScoreTickerCount,
        SchedulerCadence schedulerCadence,
        SchedulerRunSummary latestRun,
        SchedulerRunSummary latestSuccessfulRun
) {
    public record SchedulerCadence(
            String automationMode,
            boolean requiresExternalProcess,
            String timezone,
            String dailyTime,
            OffsetDateTime nextScheduledAt,
            String manualRunScope
    ) {}

    public record SchedulerRunSummary(
            String status,
            String triggerType,
            OffsetDateTime startedAt,
            OffsetDateTime finishedAt,
            int totalCount,
            int successCount,
            int failedCount,
            List<String> failedTickers,
            int skippedCount,
            List<String> skippedTickers,
            String universeSha256,
            String publishStatus,
            int observationCount,
            String errorMessage
    ) {}
}
