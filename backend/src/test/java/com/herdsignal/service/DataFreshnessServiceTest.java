package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.domain.SchedulerRun;
import com.herdsignal.dto.DataFreshnessResponse;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.HerdObservationRepository;
import com.herdsignal.repository.SchedulerRunRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class DataFreshnessServiceTest {
    private SchedulerRunRepository schedulerRunRepository;
    private DailyPriceRepository dailyPriceRepository;
    private HerdObservationRepository herdObservationRepository;
    private DataFreshnessService service;

    @BeforeEach
    void setUp() {
        schedulerRunRepository = mock(SchedulerRunRepository.class);
        dailyPriceRepository = mock(DailyPriceRepository.class);
        herdObservationRepository = mock(HerdObservationRepository.class);
        Clock clock = Clock.fixed(Instant.parse("2026-07-15T03:00:00Z"), ZoneOffset.UTC);
        service = new DataFreshnessService(
                schedulerRunRepository,
                dailyPriceRepository,
                herdObservationRepository,
                new ObjectMapper(),
                clock
        );
    }

    @Test
    void returnsFreshWhenSuccessfulRunAndRecentDataExist() {
        SchedulerRun successfulRun = run("SUCCESS");
        when(dailyPriceRepository.findLatestPriceDate()).thenReturn(Optional.of(LocalDate.of(2026, 7, 14)));
        mockObservationDate(LocalDate.of(2026, 7, 11));
        mockCoverage(LocalDate.of(2026, 7, 14), 12);
        when(schedulerRunRepository.findTopByJobNameOrderByStartedAtDesc("HERD_TIER1_DAILY"))
                .thenReturn(Optional.of(successfulRun));
        when(schedulerRunRepository.findTopByJobNameAndStatusOrderByFinishedAtDesc(
                "HERD_TIER1_DAILY", "SUCCESS"))
                .thenReturn(Optional.of(successfulRun));

        DataFreshnessResponse response = service.getStatus();

        assertThat(response.status()).isEqualTo("FRESH");
        assertThat(response.priceBusinessDaysOld()).isEqualTo(1);
        assertThat(response.latestRun().failedTickers()).isEmpty();
        assertThat(response.latestSuccessfulRun().status()).isEqualTo("SUCCESS");
        assertThat(response.latestSuccessfulRun().publishStatus()).isEqualTo("SUCCESS");
        assertThat(response.latestSuccessfulRun().universeSha256()).hasSize(64);
    }

    @Test
    void returnsWarningWhenLatestRunPartiallyFailed() {
        SchedulerRun partialRun = run("PARTIAL_FAILURE");
        when(dailyPriceRepository.findLatestPriceDate()).thenReturn(Optional.of(LocalDate.of(2026, 7, 14)));
        mockObservationDate(LocalDate.of(2026, 7, 11));
        mockCoverage(LocalDate.of(2026, 7, 14), 12);
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
        mockObservationDate(LocalDate.of(2026, 7, 3));
        mockCoverage(LocalDate.of(2026, 7, 9), 12);
        when(schedulerRunRepository.findTopByJobNameOrderByStartedAtDesc("HERD_TIER1_DAILY"))
                .thenReturn(Optional.of(successfulRun));

        assertThat(service.getStatus().status()).isEqualTo("STALE");
    }

    @Test
    void returnsFailedWhenSchedulerRunIsStuck() {
        SchedulerRun running = run("RUNNING");
        when(running.getStartedAt()).thenReturn(LocalDateTime.of(2026, 7, 15, 0, 0));
        when(dailyPriceRepository.findLatestPriceDate()).thenReturn(Optional.of(LocalDate.of(2026, 7, 14)));
        mockObservationDate(LocalDate.of(2026, 7, 11));
        mockCoverage(LocalDate.of(2026, 7, 14), 12);
        when(schedulerRunRepository.findTopByJobNameOrderByStartedAtDesc("HERD_TIER1_DAILY"))
                .thenReturn(Optional.of(running));

        assertThat(service.getStatus().status()).isEqualTo("FAILED");
    }

    @Test
    void returnsFailedWhenLatestSchedulerRunFailed() {
        SchedulerRun failed = run("FAILED");
        when(dailyPriceRepository.findLatestPriceDate()).thenReturn(Optional.of(LocalDate.of(2026, 7, 14)));
        mockObservationDate(LocalDate.of(2026, 7, 11));
        mockCoverage(LocalDate.of(2026, 7, 14), 12);
        when(schedulerRunRepository.findTopByJobNameOrderByStartedAtDesc("HERD_TIER1_DAILY"))
                .thenReturn(Optional.of(failed));

        assertThat(service.getStatus().status()).isEqualTo("FAILED");
    }

    @Test
    void usesLatestRunCoverageInsteadOfComparingEveryTickerToOneGlobalPriceDate() {
        SchedulerRun successfulRun = run("SUCCESS");
        LocalDate latestDate = LocalDate.of(2026, 7, 14);
        when(dailyPriceRepository.findLatestPriceDate()).thenReturn(Optional.of(latestDate));
        mockObservationDate(latestDate);
        when(herdObservationRepository.countDistinctTickersByObservationDate(
                "HERD_STATE_S1", latestDate)).thenReturn(9L);
        mockCoverage(latestDate, 9);
        when(schedulerRunRepository.findTopByJobNameOrderByStartedAtDesc("HERD_TIER1_DAILY"))
                .thenReturn(Optional.of(successfulRun));

        DataFreshnessResponse response = service.getStatus();

        assertThat(response.status()).isEqualTo("WARNING");
        assertThat(response.freshPriceTickerCount()).isEqualTo(12);
        assertThat(response.missingPriceTickerCount()).isZero();
        assertThat(response.missingObservationTickerCount()).isEqualTo(3);
    }

    @Test
    void treatsStoredSchedulerTimesAsUtc() {
        SchedulerRun running = run("RUNNING");
        when(running.getStartedAt()).thenReturn(LocalDateTime.of(2026, 7, 15, 2, 30));
        when(dailyPriceRepository.findLatestPriceDate()).thenReturn(Optional.of(LocalDate.of(2026, 7, 14)));
        mockObservationDate(LocalDate.of(2026, 7, 11));
        mockCoverage(LocalDate.of(2026, 7, 14), 12);
        when(schedulerRunRepository.findTopByJobNameOrderByStartedAtDesc("HERD_TIER1_DAILY"))
                .thenReturn(Optional.of(running));

        DataFreshnessResponse response = service.getStatus();

        assertThat(response.status()).isEqualTo("RUNNING");
        assertThat(response.latestRun().startedAt().getOffset()).isEqualTo(ZoneOffset.UTC);
    }

    private void mockCoverage(LocalDate date, long count) {
        when(dailyPriceRepository.countDistinctTickersByPriceDate(date)).thenReturn(count);
    }

    private void mockObservationDate(LocalDate date) {
        when(herdObservationRepository.findLatestObservationDate("HERD_STATE_S1"))
                .thenReturn(Optional.of(date));
        when(herdObservationRepository.countDistinctTickersByObservationDate(
                "HERD_STATE_S1", date)).thenReturn(12L);
    }

    private SchedulerRun run(String status) {
        SchedulerRun run = mock(SchedulerRun.class);
        when(run.getStatus()).thenReturn(status);
        when(run.getTriggerType()).thenReturn("MANUAL");
        when(run.getFailedTickers()).thenReturn("[]");
        when(run.getTotalCount()).thenReturn(12);
        when(run.getSuccessCount()).thenReturn(status.equals("SUCCESS") ? 12 : 11);
        when(run.getFailedCount()).thenReturn(status.equals("SUCCESS") ? 0 : 1);
        when(run.getSkippedTickers()).thenReturn("[]");
        when(run.getUniverseSha256()).thenReturn("a".repeat(64));
        when(run.getPublishStatus()).thenReturn(
                status.equals("SUCCESS") ? "SUCCESS" : "SKIPPED_INCOMPLETE_INPUT");
        when(run.getObservationCount()).thenReturn(12);
        return run;
    }
}
