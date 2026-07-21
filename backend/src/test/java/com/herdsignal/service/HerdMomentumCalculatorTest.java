package com.herdsignal.service;

import com.herdsignal.domain.HerdScore;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class HerdMomentumCalculatorTest {

    private final HerdMomentumCalculator calculator = new HerdMomentumCalculator();

    @Test
    void resultDoesNotDependOnRepositorySortOrder() {
        LocalDate latestDate = LocalDate.of(2026, 7, 21);
        HerdScore latest = score(latestDate, 70);
        List<HerdScore> descending = new ArrayList<>(List.of(
                score(latestDate.minusDays(1), 68),
                score(latestDate.minusDays(5), 64),
                score(latestDate.minusDays(20), 55),
                score(latestDate.minusDays(34), 50),
                score(latestDate.minusDays(50), 40)
        ));
        List<HerdScore> ascending = new ArrayList<>(descending);
        Collections.reverse(ascending);

        HerdMomentumCalculator.Result fromDescending = calculator.calculate(latest, descending);
        HerdMomentumCalculator.Result fromAscending = calculator.calculate(latest, ascending);

        assertThat(fromAscending).isEqualTo(fromDescending);
        assertThat(fromDescending.shortDelta()).isEqualTo(2.0);
        assertThat(fromDescending.monthDelta()).isEqualTo(20.0);
        assertThat(fromDescending.score()).isEqualTo(85);
    }

    private HerdScore score(LocalDate date, double value) {
        return HerdScore.builder()
                .ticker("TEST")
                .scoreDate(date)
                .herdScore(BigDecimal.valueOf(value))
                .herdStage("Calm")
                .signal("HOLD")
                .build();
    }
}
