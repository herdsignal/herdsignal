package com.herdsignal.service;

import com.herdsignal.domain.HerdScore;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class HerdLifecycleClassifierTest {

    private final HerdLifecycleClassifier classifier = new HerdLifecycleClassifier();

    @Test
    void classificationDoesNotDependOnHistorySortOrder() {
        LocalDate latestDate = LocalDate.of(2026, 7, 21);
        HerdScore latest = score(latestDate, "SELL");
        List<HerdScore> descending = new ArrayList<>(List.of(
                score(latestDate, "SELL"),
                score(latestDate.minusDays(1), "SELL"),
                score(latestDate.minusDays(2), "SELL"),
                score(latestDate.minusDays(3), "HOLD"),
                score(latestDate.minusDays(4), "SELL")
        ));
        List<HerdScore> ascending = new ArrayList<>(descending);
        Collections.reverse(ascending);

        HerdLifecycleClassifier.Result fromDescending = classifier.classify(latest, descending);
        HerdLifecycleClassifier.Result fromAscending = classifier.classify(latest, ascending);

        assertThat(fromAscending).isEqualTo(fromDescending);
        assertThat(fromDescending.signalDays()).isEqualTo(3);
        assertThat(fromDescending.ratioMultiplier()).isEqualTo(0.65);
    }

    private HerdScore score(LocalDate date, String signal) {
        return HerdScore.builder()
                .ticker("TEST")
                .scoreDate(date)
                .herdScore(BigDecimal.valueOf(70))
                .herdStage("Drift")
                .signal(signal)
                .build();
    }
}
