package com.herdsignal.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.domain.SchedulerRun;
import com.herdsignal.dto.DataFreshnessResponse;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.HerdScoreRepository;
import com.herdsignal.repository.SchedulerRunRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.Collections;
import java.util.List;

@Service
public class DataFreshnessService {
    private static final String JOB_NAME = "HERD_TIER1_DAILY";

    private final SchedulerRunRepository schedulerRunRepository;
    private final DailyPriceRepository dailyPriceRepository;
    private final HerdScoreRepository herdScoreRepository;
    private final ObjectMapper objectMapper;
    private final Clock clock;

    public DataFreshnessService(
            SchedulerRunRepository schedulerRunRepository,
            DailyPriceRepository dailyPriceRepository,
            HerdScoreRepository herdScoreRepository,
            ObjectMapper objectMapper) {
        this(schedulerRunRepository, dailyPriceRepository, herdScoreRepository, objectMapper,
                Clock.system(ZoneId.of("Asia/Seoul")));
    }

    DataFreshnessService(
            SchedulerRunRepository schedulerRunRepository,
            DailyPriceRepository dailyPriceRepository,
            HerdScoreRepository herdScoreRepository,
            ObjectMapper objectMapper,
            Clock clock) {
        this.schedulerRunRepository = schedulerRunRepository;
        this.dailyPriceRepository = dailyPriceRepository;
        this.herdScoreRepository = herdScoreRepository;
        this.objectMapper = objectMapper;
        this.clock = clock;
    }

    @Transactional(readOnly = true)
    public DataFreshnessResponse getStatus() {
        LocalDate today = LocalDate.now(clock);
        LocalDate latestPriceDate = dailyPriceRepository.findLatestPriceDate().orElse(null);
        LocalDate latestScoreDate = herdScoreRepository.findLatestScoreDate().orElse(null);
        SchedulerRun latestRun = schedulerRunRepository
                .findTopByJobNameOrderByStartedAtDesc(JOB_NAME)
                .orElse(null);

        Integer priceAge = businessDaysBetween(latestPriceDate, today);
        Integer scoreAge = businessDaysBetween(latestScoreDate, today);
        String status = determineStatus(latestRun, priceAge, scoreAge);

        return new DataFreshnessResponse(
                status,
                statusMessage(status),
                latestPriceDate,
                latestScoreDate,
                priceAge,
                scoreAge,
                toSummary(latestRun)
        );
    }

    private String determineStatus(SchedulerRun run, Integer priceAge, Integer scoreAge) {
        if (run != null && "RUNNING".equals(run.getStatus())) return "RUNNING";
        if (priceAge == null || scoreAge == null) return "NO_DATA";
        int maxAge = Math.max(priceAge, scoreAge);
        if (maxAge > 2) return "STALE";
        if (maxAge > 1 || run == null || !"SUCCESS".equals(run.getStatus())) return "WARNING";
        return "FRESH";
    }

    private String statusMessage(String status) {
        return switch (status) {
            case "FRESH" -> "가격과 HERD 데이터가 최신 상태입니다.";
            case "WARNING" -> "일부 데이터 또는 최근 수집 결과를 확인하세요.";
            case "STALE" -> "데이터가 오래되었습니다. 스케줄러 실행이 필요합니다.";
            case "RUNNING" -> "스케줄러가 데이터를 업데이트하고 있습니다.";
            default -> "아직 스케줄러 실행 이력이 충분하지 않습니다.";
        };
    }

    private DataFreshnessResponse.SchedulerRunSummary toSummary(SchedulerRun run) {
        if (run == null) return null;
        return new DataFreshnessResponse.SchedulerRunSummary(
                run.getStatus(),
                run.getTriggerType(),
                run.getStartedAt(),
                run.getFinishedAt(),
                valueOrZero(run.getTotalCount()),
                valueOrZero(run.getSuccessCount()),
                valueOrZero(run.getFailedCount()),
                parseFailedTickers(run.getFailedTickers()),
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
