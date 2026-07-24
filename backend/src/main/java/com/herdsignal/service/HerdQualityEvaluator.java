package com.herdsignal.service;

import com.herdsignal.domain.HerdIndicator;
import com.herdsignal.domain.HerdScore;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;

/**
 * 저장된 HERD 산출물의 데이터 완성도와 최신성을 평가한다.
 *
 * <p>시장 상태 점수의 방향성과는 독립된 품질 메타데이터이며, 조회 서비스나 개인 행동
 * 규칙이 품질 계산 세부사항을 복제하지 않도록 한곳에 둔다.</p>
 */
@Component
public class HerdQualityEvaluator {

    public HerdQuality evaluate(HerdScore score, HerdIndicator indicator) {
        List<String> flags = new ArrayList<>();
        List<String> reasons = new ArrayList<>();
        int qualityScore = 0;

        int activeIndicatorCount = countPresentIndicators(indicator);
        qualityScore += activeIndicatorCount * 9;
        if (activeIndicatorCount == 5) {
            flags.add("CORE_INDICATORS_COMPLETE");
            reasons.add("핵심 지표 5개 모두 계산됨");
        } else {
            flags.add("CORE_INDICATORS_PARTIAL");
            reasons.add("핵심 지표 " + activeIndicatorCount + "/5개 계산됨");
        }

        if (indicator != null && indicator.getMa200Weekly() != null) {
            qualityScore += 20;
            flags.add("MA200_WEEKLY_AVAILABLE");
            reasons.add("200주 MA 위치 지표 포함");
        } else {
            flags.add("MA200_WEEKLY_MISSING");
            reasons.add("200주 MA 위치 데이터 없음");
        }

        qualityScore += multiplierQuality(
                indicator == null ? null : indicator.getEpsMultiplier(),
                "EPS",
                "EPS 서프라이즈 보정 적용",
                "EPS 보정은 중립값",
                "EPS 보정 데이터 없음",
                flags,
                reasons
        );
        qualityScore += multiplierQuality(
                indicator == null ? null : indicator.getSectorMultiplier(),
                "SECTOR",
                "섹터 상대 강도 보정 적용",
                "섹터 강도 보정은 중립값",
                "섹터 강도 보정 데이터 없음",
                flags,
                reasons
        );

        long scoreAgeDays = ChronoUnit.DAYS.between(score.getScoreDate(), LocalDate.now());
        if (scoreAgeDays > 14) {
            flags.add("SCORE_STALE");
            reasons.add("HERD 점수가 14일 이상 갱신되지 않음");
        } else if (scoreAgeDays > 7) {
            qualityScore += 8;
            flags.add("SCORE_AGING");
            reasons.add("HERD 점수가 7일 이상 갱신되지 않음");
        } else {
            qualityScore += 15;
            flags.add("SCORE_FRESH");
            reasons.add("최근 7일 이내 HERD 점수");
        }

        qualityScore = Math.max(0, Math.min(100, qualityScore));
        String level = qualityLevel(qualityScore);
        return new HerdQuality(
                qualityScore,
                level,
                qualityLabel(level),
                qualitySummary(level, activeIndicatorCount, flags),
                List.copyOf(flags),
                List.copyOf(reasons)
        );
    }

    private int multiplierQuality(
            BigDecimal value,
            String flagPrefix,
            String appliedReason,
            String neutralReason,
            String missingReason,
            List<String> flags,
            List<String> reasons
    ) {
        if (value == null) {
            flags.add(flagPrefix + "_MULTIPLIER_MISSING");
            reasons.add(missingReason);
            return 0;
        }
        if (value.compareTo(BigDecimal.ONE) != 0) {
            flags.add(flagPrefix + "_MULTIPLIER_APPLIED");
            reasons.add(appliedReason);
            return 10;
        }
        flags.add(flagPrefix + "_MULTIPLIER_NEUTRAL");
        reasons.add(neutralReason);
        return 8;
    }

    private int countPresentIndicators(HerdIndicator indicator) {
        if (indicator == null) {
            return 0;
        }
        int count = 0;
        if (indicator.getMonthlyRsi() != null) count++;
        if (indicator.getWeeklyRsi() != null) count++;
        if (indicator.getPosition52w() != null) count++;
        if (indicator.getMa200Deviation() != null) count++;
        if (indicator.getMa200Weekly() != null) count++;
        return count;
    }

    private String qualityLevel(int score) {
        if (score >= 85) return "HIGH";
        if (score >= 65) return "GOOD";
        if (score >= 45) return "LIMITED";
        return "LOW";
    }

    private String qualityLabel(String level) {
        return switch (level) {
            case "HIGH" -> "신뢰도 높음";
            case "GOOD" -> "신뢰도 보통";
            case "LIMITED" -> "제한적";
            default -> "참고용";
        };
    }

    private String qualitySummary(String level, int activeIndicatorCount, List<String> flags) {
        if ("HIGH".equals(level)) {
            return "핵심 지표와 보정 데이터가 충분해 HERD 판단을 강하게 참고할 수 있습니다.";
        }
        if ("GOOD".equals(level)) {
            return "핵심 지표는 충분하지만 일부 보정은 중립 또는 제한적으로 반영됩니다.";
        }
        if ("LIMITED".equals(level)) {
            if (flags.contains("MA200_WEEKLY_MISSING")) {
                return "장기 추세 지표 일부가 부족해 HERD 판단은 보조 신호로 보는 편이 좋습니다.";
            }
            return "일부 핵심 지표가 부족해 HERD 판단은 보조 신호로 보는 편이 좋습니다.";
        }
        if (activeIndicatorCount < 3) {
            return "데이터가 부족해 현재 HERD 점수는 참고용으로만 활용하는 것이 좋습니다.";
        }
        return "신뢰도 낮음 구간으로, 포지션 크기를 작게 두고 추가 확인이 필요합니다.";
    }

    public record HerdQuality(
            int score,
            String level,
            String label,
            String summary,
            List<String> flags,
            List<String> reasons
    ) {
    }
}
