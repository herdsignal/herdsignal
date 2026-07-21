package com.herdsignal.service;

import com.herdsignal.domain.HerdScore;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.List;

/** HERD 점수 이력의 변화와 가속도를 계산한다. */
final class HerdMomentumCalculator {

    Result calculate(HerdScore latest, List<HerdScore> history) {
        if (history == null || history.size() < 2 || latest.getScoreDate() == null) {
            return new Result(50, 0.0, 0.0, 0.0, 0, "HERD 변화 데이터 부족",
                    List.of("HERD 변화율 데이터가 부족해 현재 점수 중심으로 해석합니다."));
        }
        HerdScore previous = null;
        HerdScore monthAgo = null;
        LocalDate latestDate = latest.getScoreDate();
        for (HerdScore row : history) {
            if (row.getScoreDate() == null || !row.getScoreDate().isBefore(latestDate)) continue;
            if (previous == null || row.getScoreDate().isAfter(previous.getScoreDate())) {
                previous = row;
            }
            if (ChronoUnit.DAYS.between(row.getScoreDate(), latestDate) <= 35
                    && (monthAgo == null || row.getScoreDate().isBefore(monthAgo.getScoreDate()))) {
                monthAgo = row;
            }
        }
        if (previous == null) {
            return new Result(50, 0.0, 0.0, 0.0, history.size(), "HERD 변화 데이터 부족",
                    List.of("직전 HERD 포인트가 없어 변화율을 보수적으로 봅니다."));
        }

        HerdScore baseline = monthAgo != null ? monthAgo : previous;
        double latestValue = latest.getHerdScore().doubleValue();
        double shortDelta = latestValue - previous.getHerdScore().doubleValue();
        double monthDelta = latestValue - baseline.getHerdScore().doubleValue();
        HerdScore fiveDay = scoreNearDays(history, latestDate, 5);
        HerdScore twentyDay = scoreNearDays(history, latestDate, 20);
        double fastDelta = fiveDay == null ? shortDelta : latestValue - fiveDay.getHerdScore().doubleValue();
        double slowDelta = twentyDay == null ? monthDelta : latestValue - twentyDay.getHerdScore().doubleValue();
        double acceleration = fastDelta - slowDelta / 4.0;
        int score = monthDelta >= 12 ? 85 : monthDelta >= 5 ? 70
                : monthDelta <= -12 ? 15 : monthDelta <= -5 ? 30 : 50;
        String direction = monthDelta > 1 ? "상승" : monthDelta < -1 ? "둔화" : "유지";
        String reason = String.format("HERD 5일 %.1fpt · 20일 %.1fpt · 가속도 %.1f(%s)",
                fastDelta, slowDelta, acceleration, direction);
        return new Result(score, shortDelta, monthDelta, acceleration, history.size(), reason, List.of());
    }

    private HerdScore scoreNearDays(List<HerdScore> history, LocalDate latestDate, int days) {
        LocalDate target = latestDate.minusDays(days);
        return history.stream()
                .filter(row -> row.getScoreDate() != null && row.getHerdScore() != null
                        && row.getScoreDate().isBefore(latestDate))
                .min((left, right) -> Long.compare(
                        Math.abs(ChronoUnit.DAYS.between(left.getScoreDate(), target)),
                        Math.abs(ChronoUnit.DAYS.between(right.getScoreDate(), target))))
                .orElse(null);
    }

    record Result(int score, double shortDelta, double monthDelta, double acceleration,
                  int observations, String reason, List<String> warnings) {
    }
}
