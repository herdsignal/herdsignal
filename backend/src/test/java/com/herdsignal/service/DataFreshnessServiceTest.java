package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.domain.SchedulerRun;
import com.herdsignal.dto.DataFreshnessResponse;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.HerdScoreRepository;
import com.herdsignal.repository.SchedulerRunRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class DataFreshnessServiceTest {
    private SchedulerRunRepository schedulerRunRepository;
    private DailyPriceRepository dailyPriceRepository;
    private HerdScoreRepository herdScoreRepository;
    private DataFreshnessService service;

    @BeforeEach
    void setUp() {
        schedulerRunRepository = mock(SchedulerRunRepository.class);
        dailyPriceRepository = mock(DailyPriceRepository.class);
        herdScoreRepository = mock(HerdScoreRepository.class);
        Clock clock = Clock.fixed(Instant.parse("2026-07-15T03:00:00Z"), ZoneId.of("Asia/Seoul"));
        service = new DataFreshnessService(
                schedulerRunRepository,
                dailyPriceRepository,
                herdScoreRepository,
                new ObjectMapper(),
                clock
        );
    }

    @Test
    void returnsFreshWhenSuccessfulRunAndRecentDataExist() {
        SchedulerRun successfulRun = run("SUCCESS");
        when(dailyPriceRepository.findLatestPriceDate()).thenReturn(Optional.of(LocalDate.of(2026, 7, 14)));
        when(herdScoreRepository.findLatestScoreDate()).thenReturn(Optional.of(LocalDate.of(2026, 7, 14)));
        when(schedulerRunRepository.findTopByJobNameOrderByStartedAtDesc("HERD_TIER1_DAILY"))
                .thenReturn(Optional.of(successfulRun));

        DataFreshnessResponse response = service.getStatus();

        assertThat(response.status()).isEqualTo("FRESH");
        assertThat(response.priceBusinessDaysOld()).isEqualTo(1);
        assertThat(response.latestRun().failedTickers()).isEmpty();
    }

    @Test
    void returnsWarningWhenLatestRunPartiallyFailed() {
        SchedulerRun partialRun = run("PARTIAL_FAILURE");
        when(dailyPriceRepository.findLatestPriceDate()).thenReturn(Optional.of(LocalDate.of(2026, 7, 14)));
        when(herdScoreRepository.findLatestScoreDate()).thenReturn(Optional.of(LocalDate.of(2026, 7, 14)));
        when(schedulerRunRepository.findTopByJobNameOrderByStartedAtDesc("HERD_TIER1_DAILY"))
                .thenReturn(Optional.of(partialRun));

        assertThat(service.getStatus().status()).isEqualTo("WARNING");
    }

    @Test
    void excludesWeekendFromDataAge() {
        assertThat(DataFreshnessService.businessDaysBetween(
                LocalDate.of(2026, 7, 10),
                LocalDate.of(2026, 7, 13)
        )).isEqualTo(1);
    }

    @Test
    void returnsStaleWhenDataIsMoreThanTwoBusinessDaysOld() {
        SchedulerRun successfulRun = run("SUCCESS");
        when(dailyPriceRepository.findLatestPriceDate()).thenReturn(Optional.of(LocalDate.of(2026, 7, 9)));
        when(herdScoreRepository.findLatestScoreDate()).thenReturn(Optional.of(LocalDate.of(2026, 7, 9)));
        when(schedulerRunRepository.findTopByJobNameOrderByStartedAtDesc("HERD_TIER1_DAILY"))
                .thenReturn(Optional.of(successfulRun));

        assertThat(service.getStatus().status()).isEqualTo("STALE");
    }

    @Test
    void returnsFailedWhenSchedulerRunIsStuck() {
        SchedulerRun running = run("RUNNING");
        when(running.getStartedAt()).thenReturn(LocalDateTime.of(2026, 7, 15, 9, 0));
        when(dailyPriceRepository.findLatestPriceDate()).thenReturn(Optional.of(LocalDate.of(2026, 7, 14)));
        when(herdScoreRepository.findLatestScoreDate()).thenReturn(Optional.of(LocalDate.of(2026, 7, 14)));
        when(schedulerRunRepository.findTopByJobNameOrderByStartedAtDesc("HERD_TIER1_DAILY"))
                .thenReturn(Optional.of(running));

        assertThat(service.getStatus().status()).isEqualTo("FAILED");
    }

    @Test
    void returnsFailedWhenLatestSchedulerRunFailed() {
        SchedulerRun failed = run("FAILED");
        when(dailyPriceRepository.findLatestPriceDate()).thenReturn(Optional.of(LocalDate.of(2026, 7, 14)));
        when(herdScoreRepository.findLatestScoreDate()).thenReturn(Optional.of(LocalDate.of(2026, 7, 14)));
        when(schedulerRunRepository.findTopByJobNameOrderByStartedAtDesc("HERD_TIER1_DAILY"))
                .thenReturn(Optional.of(failed));

        assertThat(service.getStatus().status()).isEqualTo("FAILED");
    }

    private SchedulerRun run(String status) {
        SchedulerRun run = mock(SchedulerRun.class);
        when(run.getStatus()).thenReturn(status);
        when(run.getTriggerType()).thenReturn("MANUAL");
        when(run.getFailedTickers()).thenReturn("[]");
        when(run.getTotalCount()).thenReturn(12);
        when(run.getSuccessCount()).thenReturn(status.equals("SUCCESS") ? 12 : 11);
        when(run.getFailedCount()).thenReturn(status.equals("SUCCESS") ? 0 : 1);
        return run;
    }
}
