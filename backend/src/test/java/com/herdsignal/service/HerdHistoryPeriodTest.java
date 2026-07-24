package com.herdsignal.service;

import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;

class HerdHistoryPeriodTest {

    private static final LocalDate TODAY = LocalDate.of(2026, 7, 24);

    @Test
    void supportsOnlyBoundedUiPeriods() {
        assertThat(HerdHistoryPeriod.cutoff("1m", TODAY)).isEqualTo(TODAY.minusMonths(1));
        assertThat(HerdHistoryPeriod.cutoff("6m", TODAY)).isEqualTo(TODAY.minusMonths(6));
        assertThat(HerdHistoryPeriod.cutoff("1y", TODAY)).isEqualTo(TODAY.minusYears(1));
        assertThat(HerdHistoryPeriod.cutoff("3y", TODAY)).isEqualTo(TODAY.minusYears(3));
    }

    @Test
    void fallsBackForUnboundedOrMalformedPeriods() {
        assertThat(HerdHistoryPeriod.cutoff("999999999999y", TODAY))
                .isEqualTo(TODAY.minusYears(3));
        assertThat(HerdHistoryPeriod.cutoff("../all", TODAY))
                .isEqualTo(TODAY.minusYears(3));
    }
}
