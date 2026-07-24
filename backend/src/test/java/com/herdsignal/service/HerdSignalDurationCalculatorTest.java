package com.herdsignal.service;

import com.herdsignal.domain.HerdScore;
import com.herdsignal.dto.HerdScoreResponse;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class HerdSignalDurationCalculatorTest {

    private final HerdSignalDurationCalculator calculator =
            new HerdSignalDurationCalculator();

    @Test
    void calculatesSignalAndStageRunsIndependently() {
        LocalDate latestDate = LocalDate.of(2026, 7, 24);
        HerdScore latest = score(latestDate, "HOLD", "Rush");
        List<HerdScore> descendingHistory = List.of(
                latest,
                score(latestDate.minusDays(1), "HOLD", "Rush"),
                score(latestDate.minusDays(2), "HOLD", "Drift"),
                score(latestDate.minusDays(3), "BUY", "Drift")
        );

        HerdScoreResponse.SignalDuration duration =
                calculator.calculate(latest, descendingHistory);

        assertThat(duration.getSignalStartedAt()).isEqualTo(latestDate.minusDays(2));
        assertThat(duration.getSignalDurationDays()).isEqualTo(3);
        assertThat(duration.getStageStartedAt()).isEqualTo(latestDate.minusDays(1));
        assertThat(duration.getStageDurationDays()).isEqualTo(2);
    }

    private HerdScore score(LocalDate date, String signal, String stage) {
        return HerdScore.builder()
                .ticker("NVDA")
                .scoreDate(date)
                .herdScore(BigDecimal.valueOf(75))
                .signal(signal)
                .herdStage(stage)
                .build();
    }
}
