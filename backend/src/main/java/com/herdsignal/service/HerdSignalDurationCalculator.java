package com.herdsignal.service;

import com.herdsignal.domain.HerdScore;
import com.herdsignal.dto.HerdScoreResponse;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.List;

/**
 * 최신 HERD 신호와 단계가 연속해서 유지된 기간을 계산한다.
 */
@Component
public class HerdSignalDurationCalculator {

    public HerdScoreResponse.SignalDuration calculate(
            HerdScore latestScore,
            List<HerdScore> history
    ) {
        LocalDate signalStartedAt = latestScore.getScoreDate();
        LocalDate stageStartedAt = latestScore.getScoreDate();
        String latestSignal = normalizeSignal(latestScore.getSignal());
        String latestStage = normalize(latestScore.getHerdStage());

        for (HerdScore row : history) {
            if (row.getScoreDate().isAfter(latestScore.getScoreDate())) {
                continue;
            }
            if (!normalizeSignal(row.getSignal()).equals(latestSignal)) {
                break;
            }
            signalStartedAt = row.getScoreDate();
        }

        for (HerdScore row : history) {
            if (row.getScoreDate().isAfter(latestScore.getScoreDate())) {
                continue;
            }
            if (!normalize(row.getHerdStage()).equals(latestStage)) {
                break;
            }
            stageStartedAt = row.getScoreDate();
        }

        return HerdScoreResponse.SignalDuration.builder()
                .signalStartedAt(signalStartedAt)
                .signalDurationDays(daysInclusive(signalStartedAt, latestScore.getScoreDate()))
                .stageStartedAt(stageStartedAt)
                .stageDurationDays(daysInclusive(stageStartedAt, latestScore.getScoreDate()))
                .build();
    }

    private String normalizeSignal(String signal) {
        return normalize(signal == null || signal.isBlank() ? "HOLD" : signal);
    }

    private String normalize(String value) {
        return value == null ? "" : value.trim().toUpperCase();
    }

    private int daysInclusive(LocalDate start, LocalDate end) {
        return (int) ChronoUnit.DAYS.between(start, end) + 1;
    }
}
