package com.herdsignal.service;

import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;

class UsMarketSessionClockTest {

    @Test
    void usesPreviousSessionBeforeNewYorkMarketClose() {
        Clock clock = Clock.fixed(Instant.parse("2026-07-24T17:00:00Z"), ZoneOffset.UTC);

        assertThat(new UsMarketSessionClock(clock).currentSessionDate())
                .isEqualTo(LocalDate.of(2026, 7, 23));
    }

    @Test
    void usesCurrentSessionAfterNewYorkMarketClose() {
        Clock clock = Clock.fixed(Instant.parse("2026-07-24T20:30:00Z"), ZoneOffset.UTC);

        assertThat(new UsMarketSessionClock(clock).currentSessionDate())
                .isEqualTo(LocalDate.of(2026, 7, 24));
    }

    @Test
    void rollsWeekendBackToFriday() {
        Clock clock = Clock.fixed(Instant.parse("2026-07-26T18:00:00Z"), ZoneOffset.UTC);

        assertThat(new UsMarketSessionClock(clock).currentSessionDate())
                .isEqualTo(LocalDate.of(2026, 7, 24));
    }
}
