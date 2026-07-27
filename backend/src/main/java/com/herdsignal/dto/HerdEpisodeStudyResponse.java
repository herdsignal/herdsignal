package com.herdsignal.dto;

import java.util.List;

public record HerdEpisodeStudyResponse(
        String availabilityStatus,
        String evidenceStatus,
        String ticker,
        String herdStage,
        String stateModelVersion,
        int minimumCompletedEpisodes,
        int episodeCount,
        List<HerdEpisodeHorizonSummary> summaries,
        List<HerdEpisodeOutcome> episodes
) {
}
