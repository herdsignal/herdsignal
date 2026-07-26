package com.herdsignal.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.domain.SchedulerRun;
import com.herdsignal.dto.DataFreshnessResponse;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.HerdObservationRepository;
import com.herdsignal.repository.SchedulerRunRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Collections;
import java.util.List;

@Service
public class DataFreshnessService {
    private static final String JOB_NAME = "HERD_TIER1_DAILY";
    private static final String STATE_MODEL_VERSION = "HERD_STATE_S1";
    private static final int MAX_RUNNING_HOURS = 2;
    private static final int PRICE_WARNING_AFTER_BUSINESS_DAYS = 1;
    private static final int PRICE_STALE_AFTER_BUSINESS_DAYS = 2;
    private static final int OBSERVATION_WARNING_AFTER_BUSINESS_DAYS = 5;
    private static final int OBSERVATION_STALE_AFTER_BUSINESS_DAYS = 7;

    private final SchedulerRunRepository schedulerRunRepository;
    private final DailyPriceRepository dailyPriceRepository;
    private final HerdObservationRepository herdObservationRepository;
    private final ObjectMapper objectMapper;
    private final Clock clock;

    @Autowired
    public DataFreshnessService(
            SchedulerRunRepository schedulerRunRepository,
            DailyPriceRepository dailyPriceRepository,
            HerdObservationRepository herdObservationRepository,
            ObjectMapper objectMapper) {
        this(schedulerRunRepository, dailyPriceRepository, herdObservationRepository, objectMapper,
                Clock.systemUTC());
    }

    DataFreshnessService(
            SchedulerRunRepository schedulerRunRepository,
            DailyPriceRepository dailyPriceRepository,
            HerdObservationRepository herdObservationRepository,
            ObjectMapper objectMapper,
            Clock clock) {
        this.schedulerRunRepository = schedulerRunRepository;
        this.dailyPriceRepository = dailyPriceRepository;
        this.herdObservationRepository = herdObservationRepository;
        this.objectMapper = objectMapper;
        this.clock = clock;
    }

    @Transactional(readOnly = true)
    public DataFreshnessResponse getStatus() {
        LocalDate today = LocalDate.now(clock);
        LocalDate latestPriceDate = dailyPriceRepository.findLatestPriceDate().orElse(null);
        LocalDate latestObservationDate = herdObservationRepository
                .findLatestObservationDate(STATE_MODEL_VERSION)
                .orElse(null);
        SchedulerRun latestRun = schedulerRunRepository
                .findTopByJobNameOrderByStartedAtDesc(JOB_NAME)
                .orElse(null);
        SchedulerRun latestSuccessfulRun = schedulerRunRepository
                .findTopByJobNameAndStatusOrderByFinishedAtDesc(
                        JOB_NAME, "SUCCESS")
                .orElse(null);

        Integer priceAge = businessDaysBetween(latestPriceDate, today);
        Integer observationAge = businessDaysBetween(latestObservationDate, today);
        int expectedTickerCount = latestRun != null ? valueOrZero(latestRun.getTotalCount()) : 0;
        int freshPriceTickerCount = countPriceTickers(latestPriceDate);
        int freshObservationTickerCount = countObservationTickers(latestObservationDate);
        int expectedObservationTickerCount = expectedObservationCount(
                latestRun, freshObservationTickerCount);
        int missingPriceTickerCount = missingCount(expectedTickerCount, freshPriceTickerCount);
        int missingObservationTickerCount = missingCount(
                expectedObservationTickerCount, freshObservationTickerCount);
        String status = determineStatus(
                latestRun,
                priceAge,
                observationAge,
                missingPriceTickerCount,
                missingObservationTickerCount
        );

        return new DataFreshnessResponse(
                status,
                statusMessage(status),
                latestPriceDate,
                latestObservationDate,
                latestObservationDate,
                priceAge,
                observationAge,
                observationAge,
                expectedTickerCount,
                freshPriceTickerCount,
                expectedObservationTickerCount,
                freshObservationTickerCount,
                missingObservationTickerCount,
                freshObservationTickerCount,
                missingPriceTickerCount,
                missingObservationTickerCount,
                toSummary(latestRun),
                toSummary(latestSuccessfulRun)
        );
    }

    private String determineStatus(
            SchedulerRun run,
            Integer priceAge,
            Integer observationAge,
            int missingPriceTickerCount,
            int missingObservationTickerCount
    ) {
        if (run != null && "RUNNING".equals(run.getStatus())) {
            LocalDateTime staleBoundary = LocalDateTime.ofInstant(
                    clock.instant().minusSeconds(MAX_RUNNING_HOURS * 3600L),
                    ZoneOffset.UTC
            );
            return run.getStartedAt().isBefore(staleBoundary) ? "FAILED" : "RUNNING";
        }
        if (run != null && "FAILED".equals(run.getStatus())) return "FAILED";
        if (priceAge == null || observationAge == null) return "NO_DATA";
        if (priceAge > PRICE_STALE_AFTER_BUSINESS_DAYS
                || observationAge > OBSERVATION_STALE_AFTER_BUSINESS_DAYS) {
            return "STALE";
        }
        if (priceAge > PRICE_WARNING_AFTER_BUSINESS_DAYS
                || observationAge > OBSERVATION_WARNING_AFTER_BUSINESS_DAYS
                || missingPriceTickerCount > 0
                || missingObservationTickerCount > 0
                || run == null
                || !"SUCCESS".equals(run.getStatus())) {
            return "WARNING";
        }
        return "FRESH";
    }

    private String statusMessage(String status) {
        return switch (status) {
            case "FRESH" -> "가격과 HERD 데이터가 최신 상태입니다.";
            case "WARNING" -> "일부 데이터 또는 최근 수집 결과를 확인하세요.";
            case "STALE" -> "데이터가 오래되었습니다. 스케줄러 실행이 필요합니다.";
            case "RUNNING" -> "스케줄러가 데이터를 업데이트하고 있습니다.";
            case "FAILED" -> "최근 스케줄러 실행이 실패했거나 비정상적으로 오래 실행 중입니다.";
            default -> "아직 스케줄러 실행 이력이 충분하지 않습니다.";
        };
    }

    private DataFreshnessResponse.SchedulerRunSummary toSummary(SchedulerRun run) {
        if (run == null) return null;
        return new DataFreshnessResponse.SchedulerRunSummary(
                run.getStatus(),
                run.getTriggerType(),
                asUtc(run.getStartedAt()),
                asUtc(run.getFinishedAt()),
                valueOrZero(run.getTotalCount()),
                valueOrZero(run.getSuccessCount()),
                valueOrZero(run.getFailedCount()),
                parseFailedTickers(run.getFailedTickers()),
                valueOrZero(run.getSkippedCount()),
                parseFailedTickers(run.getSkippedTickers()),
                run.getUniverseSha256(),
                run.getPublishStatus(),
                valueOrZero(run.getObservationCount()),
                run.getErrorMessage()
        );
    }

    private List<String> parseFailedTickers(String json) {
        if (json == null || json.isBlank()) return Collections.emptyList();
        try {
            return objectMapper.readValue(json, new TypeReference<>() {});
        } catch (Exception ignored) {
            return Collections.emptyList();
        }
    }

    private int valueOrZero(Integer value) {
        return value == null ? 0 : value;
    }

    private int countPriceTickers(LocalDate latestPriceDate) {
        return latestPriceDate == null
                ? 0
                : Math.toIntExact(dailyPriceRepository.countDistinctTickersByPriceDate(latestPriceDate));
    }

    private int countObservationTickers(LocalDate latestObservationDate) {
        return latestObservationDate == null
                ? 0
                : Math.toIntExact(herdObservationRepository
                        .countDistinctTickersByObservationDate(
                                STATE_MODEL_VERSION, latestObservationDate));
    }

    private int expectedObservationCount(SchedulerRun run, int actual) {
        if (run == null || run.getObservationCount() == null) {
            return actual;
        }
        return Math.max(0, run.getObservationCount());
    }

    private int missingCount(int expected, int actual) {
        return Math.max(0, expected - actual);
    }

    private OffsetDateTime asUtc(LocalDateTime value) {
        return value == null ? null : value.atOffset(ZoneOffset.UTC);
    }

    static Integer businessDaysBetween(LocalDate dataDate, LocalDate today) {
        if (dataDate == null) return null;
        if (!dataDate.isBefore(today)) return 0;
        int days = 0;
        for (LocalDate date = dataDate.plusDays(1); !date.isAfter(today); date = date.plusDays(1)) {
            if (date.getDayOfWeek() != DayOfWeek.SATURDAY && date.getDayOfWeek() != DayOfWeek.SUNDAY) {
                days++;
            }
        }
        return days;
    }
}
