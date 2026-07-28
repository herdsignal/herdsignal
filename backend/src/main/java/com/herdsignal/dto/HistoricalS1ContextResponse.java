package com.herdsignal.dto;

import java.time.LocalDate;
import java.util.List;

public record HistoricalS1ContextResponse(
        String availabilityStatus,
        String evidenceStatus,
        String contextScope,
        String ticker,
        String herdStage,
        String stateModelVersion,
        LocalDate historyStartDate,
        LocalDate historyEndDate,
        boolean survivorshipSafe,
        int minimumCompletedEpisodes,
        int episodeCount,
        List<HistoricalS1ContextSummary> summaries,
        boolean directionPrediction,
        String operationalAction,
        double operationalActionRatio
) {
}
