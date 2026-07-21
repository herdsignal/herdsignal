package com.herdsignal.service;

import com.herdsignal.domain.HerdScore;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.List;

/** 같은 HERD 신호의 지속 기간을 행동 강도와 분리해 분류한다. */
final class HerdLifecycleClassifier {

    Result classify(HerdScore latest, List<HerdScore> history) {
        if (latest.getScoreDate() == null || history == null || history.isEmpty()) {
            return new Result(0, 1.0, 0, "신호 지속일 데이터 부족", List.of());
        }
        String latestSignal = normalized(latest.getSignal());
        LocalDate startedAt = latest.getScoreDate();
        List<HerdScore> ordered = history.stream()
                .filter(row -> row.getScoreDate() != null
                        && !row.getScoreDate().isAfter(latest.getScoreDate()))
                .sorted((left, right) -> right.getScoreDate().compareTo(left.getScoreDate()))
                .toList();
        for (HerdScore row : ordered) {
            if (normalized(row.getSignal()).equals(latestSignal)) startedAt = row.getScoreDate();
            else break;
        }

        long days = Math.max(1, ChronoUnit.DAYS.between(startedAt, latest.getScoreDate()) + 1);
        if (days <= 5) {
            return new Result(days, 0.65, -8, "신호 초입 " + days + "일째",
                    List.of("초입 신호는 확인 전까지 행동 비율을 낮춥니다."));
        }
        if (days <= 20) return new Result(days, 1.0, 4, "신호 진행 " + days + "일째", List.of());
        if (days <= 45) {
            return new Result(days, 0.82, -3, "신호 성숙 " + days + "일째",
                    List.of("이미 진행된 신호라 신규 행동은 분할 기준으로 제한합니다."));
        }
        return new Result(days, 0.55, -10, "신호 장기 지속 " + days + "일째",
                List.of("장기 지속 신호는 추격 대응보다 다음 전환 확인이 우선입니다."));
    }

    private String normalized(String signal) {
        return signal == null || signal.isBlank() ? "HOLD" : signal.trim().toUpperCase();
    }

    record Result(long signalDays, double ratioMultiplier, int scoreAdjustment,
                  String reason, List<String> warnings) {
    }
}
