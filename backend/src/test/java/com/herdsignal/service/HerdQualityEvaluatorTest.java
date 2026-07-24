package com.herdsignal.service;

import com.herdsignal.domain.HerdIndicator;
import com.herdsignal.domain.HerdScore;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;

class HerdQualityEvaluatorTest {

    private final HerdQualityEvaluator evaluator = new HerdQualityEvaluator();

    @Test
    void ratesCompleteFreshOutputAsHighQuality() {
        HerdIndicator indicator = HerdIndicator.builder()
                .monthlyRsi(BigDecimal.TEN)
                .weeklyRsi(BigDecimal.TEN)
                .position52w(BigDecimal.TEN)
                .ma200Deviation(BigDecimal.TEN)
                .ma200Weekly(BigDecimal.TEN)
                .epsMultiplier(BigDecimal.ONE)
                .sectorMultiplier(BigDecimal.ONE)
                .build();

        HerdQualityEvaluator.HerdQuality quality =
                evaluator.evaluate(score(LocalDate.now()), indicator);

        assertThat(quality.score()).isEqualTo(96);
        assertThat(quality.level()).isEqualTo("HIGH");
        assertThat(quality.flags()).contains(
                "CORE_INDICATORS_COMPLETE",
                "MA200_WEEKLY_AVAILABLE",
                "SCORE_FRESH"
        );
    }

    @Test
    void keepsMissingOutputAtReferenceOnlyQuality() {
        HerdQualityEvaluator.HerdQuality quality =
                evaluator.evaluate(score(LocalDate.now().minusDays(30)), null);

        assertThat(quality.score()).isZero();
        assertThat(quality.level()).isEqualTo("LOW");
        assertThat(quality.flags()).contains(
                "CORE_INDICATORS_PARTIAL",
                "MA200_WEEKLY_MISSING",
                "SCORE_STALE"
        );
    }

    private HerdScore score(LocalDate date) {
        return HerdScore.builder()
                .ticker("NVDA")
                .scoreDate(date)
                .herdScore(BigDecimal.valueOf(70))
                .herdStage("Drift")
                .signal("HOLD")
                .build();
    }
}
