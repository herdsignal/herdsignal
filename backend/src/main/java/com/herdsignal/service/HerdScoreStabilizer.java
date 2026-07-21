package com.herdsignal.service;

import com.herdsignal.domain.HerdScore;

import java.time.LocalDate;
import java.util.List;

/** 5단계 경계 주변에서 하루 단위 상태 뒤집힘을 완화한다. */
final class HerdScoreStabilizer {
    private static final double[] BOUNDARIES = {15.0, 40.0, 60.0, 75.0};

    Result stabilize(double current, LocalDate latestDate, List<HerdScore> history) {
        HerdScore previous = previous(history, latestDate);
        if (previous == null || previous.getHerdScore() == null) {
            return new Result(current, "단계 안정화 비교 이력 부족");
        }
        double before = previous.getHerdScore().doubleValue();
        for (double boundary : BOUNDARIES) {
            if (Math.abs(current - boundary) <= 2.0
                    && (current - boundary) * (before - boundary) < 0) {
                double stable = before < boundary ? boundary - 0.01 : boundary + 0.01;
                return new Result(stable, String.format("경계 안정화 적용 %.1f→%.1f", before, current));
            }
        }
        return new Result(current, "단계 안정화 변동 없음");
    }

    private HerdScore previous(List<HerdScore> history, LocalDate latestDate) {
        if (history == null) return null;
        return history.stream()
                .filter(row -> row.getScoreDate() != null && row.getHerdScore() != null
                        && (latestDate == null || row.getScoreDate().isBefore(latestDate)))
                .max((left, right) -> left.getScoreDate().compareTo(right.getScoreDate()))
                .orElse(null);
    }

    record Result(double score, String reason) {
    }
}
