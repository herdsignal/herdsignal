package com.herdsignal.service;

import com.herdsignal.domain.HerdScore;
import com.herdsignal.dto.ActionDecision;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class ActionDecisionServiceTest {

    private final ActionDecisionService service = new ActionDecisionService();

    @Test
    void scalesActionRatioDownWhenDataQualityIsLow() {
        HerdScore latest = score(LocalDate.of(2026, 7, 10), 12, "Flee", "BUY");
        List<HerdScore> history = historyUntil(latest.getScoreDate(), 25, 18, "Flee", "BUY");

        ActionDecision highQuality = service.decide(latest, null, 90, history);
        ActionDecision lowQuality = service.decide(latest, null, 40, history);

        assertThat(highQuality.getActionModelVersion()).isEqualTo("HERD_v6.1");
        assertThat(highQuality.getActionModelStatus()).isEqualTo("RESEARCH_VALIDATION");
        assertThat(lowQuality.getActionRatio()).isLessThan(highQuality.getActionRatio());
    }

    @Test
    void keepsPreviousStageInsideBoundaryBuffer() {
        LocalDate latestDate = LocalDate.of(2026, 7, 10);
        HerdScore latest = score(latestDate, 41, "Calm", "HOLD");
        List<HerdScore> history = List.of(score(latestDate.minusDays(1), 39, "Scatter", "ADD"));

        ActionDecision decision = service.decide(latest, null, 90, history);

        assertThat(decision.getActionRegime()).isEqualTo("NORMAL_SCATTER");
        assertThat(decision.getActionReasons()).anyMatch(reason -> reason.contains("경계 안정화 적용"));
    }

    private static List<HerdScore> historyUntil(LocalDate latest, int count, double start, String stage, String signal) {
        List<HerdScore> rows = new ArrayList<>();
        for (int i = count; i >= 1; i--) {
            rows.add(score(latest.minusDays(i), start - i * 0.1, stage, signal));
        }
        return rows;
    }

    private static HerdScore score(LocalDate date, double value, String stage, String signal) {
        return HerdScore.builder()
                .ticker("TEST")
                .scoreDate(date)
                .herdScore(BigDecimal.valueOf(value))
                .herdStage(stage)
                .signal(signal)
                .build();
    }
}
