package com.herdsignal.service;

import com.herdsignal.domain.HerdIndicator;
import com.herdsignal.domain.HerdScore;
import com.herdsignal.dto.ActionDecision;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.List;

/**
 * HERD Action Layer 계산 서비스.
 * HERD 점수는 시장 상태를, Action Layer는 장기투자자가 움직일 강도를 담당한다.
 */
@Service
public class ActionDecisionService {

    private static final double FLEE_THRESHOLD = 15.0;
    private static final double SCATTER_UPPER = 40.0;
    private static final double DRIFT_LOWER = 60.0;
    private static final double RUSH_THRESHOLD = 75.0;

    public ActionDecision decide(HerdScore score, HerdIndicator indicator, Integer qualityScore) {
        double herdScore = score.getHerdScore().doubleValue();
        int dataQuality = qualityScore != null ? qualityScore : 50;
        TrendContext trend = calculateTrendContext(indicator);
        RegimeDecision regime = chooseRegime(herdScore, trend);
        int actionScore = calculateActionScore(herdScore, dataQuality, trend.score(), regime);

        List<String> reasons = new ArrayList<>();
        reasons.add("HERD " + displayStage(score.getHerdStage()) + " 구간");
        reasons.add("장기 추세 품질 " + trend.score() + "/100");
        reasons.add("데이터 품질 " + dataQuality + "/100");
        reasons.add(regime.reason());

        List<String> warnings = new ArrayList<>(trend.warnings());
        if (dataQuality < 65) {
            warnings.add("데이터 품질이 낮아 행동 비율을 보수적으로 해석해야 합니다.");
        }
        if (regime.ratio() == 0.0 && ("Flee".equals(displayStage(score.getHerdStage()))
                || "Scatter".equals(displayStage(score.getHerdStage())))) {
            warnings.add("낮은 HERD 점수지만 추세 훼손 가능성이 있어 관찰을 우선합니다.");
        }

        return ActionDecision.builder()
                .actionScore(actionScore)
                .actionGrade(actionGrade(actionScore, regime.ratio()))
                .actionLabel(regime.label())
                .actionRatio(BigDecimal.valueOf(regime.ratio()).setScale(2, RoundingMode.HALF_UP))
                .actionRegime(regime.code())
                .actionRegimeLabel(regime.regimeLabel())
                .actionReasons(reasons)
                .actionWarnings(warnings)
                .build();
    }

    private TrendContext calculateTrendContext(HerdIndicator indicator) {
        if (indicator == null) {
            return new TrendContext(35, 50.0, List.of("지표 분해 데이터가 없어 추세 품질을 낮게 반영합니다."));
        }

        int score = 0;
        double ma200DeviationValue = 50.0;
        List<String> warnings = new ArrayList<>();

        BigDecimal ma200Weekly = indicator.getMa200Weekly();
        if (ma200Weekly != null) {
            double value = ma200Weekly.doubleValue();
            if (value >= 60) score += 25;
            else if (value >= 40) score += 17;
            else score += 8;
        } else {
            warnings.add("200주 MA 위치 데이터가 없습니다.");
        }

        BigDecimal ma200Deviation = indicator.getMa200Deviation();
        if (ma200Deviation != null) {
            double value = ma200Deviation.doubleValue();
            ma200DeviationValue = value;
            if (value >= 35 && value <= 70) score += 20;
            else if (value >= 20 && value < 85) score += 14;
            else score += 6;

            if (value >= 85) {
                warnings.add("MA200 이격도가 높아 과밀 국면일 수 있습니다.");
            }
            if (value <= 15) {
                warnings.add("MA200 이격도가 낮아 추세 훼손 여부 확인이 필요합니다.");
            }
        }

        BigDecimal position52w = indicator.getPosition52w();
        if (position52w != null) {
            double value = position52w.doubleValue();
            if (value >= 55) score += 20;
            else if (value >= 35) score += 14;
            else score += 6;
        }

        BigDecimal sectorMultiplier = indicator.getSectorMultiplier();
        if (sectorMultiplier != null) {
            double value = sectorMultiplier.doubleValue();
            if (value <= 0.95) score += 20;
            else if (value <= 1.00) score += 14;
            else if (value <= 1.05) score += 8;
            else {
                score += 4;
                warnings.add("섹터 대비 상대 강도가 약합니다.");
            }
        } else {
            score += 8;
        }

        BigDecimal epsMultiplier = indicator.getEpsMultiplier();
        if (epsMultiplier != null) {
            double value = epsMultiplier.doubleValue();
            if (value <= 0.95) score += 15;
            else if (value <= 1.00) score += 10;
            else if (value <= 1.05) score += 6;
            else {
                score += 3;
                warnings.add("EPS 서프라이즈 흐름이 약합니다.");
            }
        } else {
            score += 6;
        }

        return new TrendContext(clamp(score, 0, 100), ma200DeviationValue, warnings);
    }

    private RegimeDecision chooseRegime(double score, TrendContext trend) {
        int trendScore = trend.score();
        double ma200Dev = trend.ma200Deviation();

        if (score >= RUSH_THRESHOLD) {
            if (trendScore >= 75) {
                return new RegimeDecision(
                        "HEALTHY_RUSH",
                        "보유 우선·소폭 리밸런싱",
                        "건강한 군중 밀집",
                        0.05,
                        "강한 추세의 Rush는 전량 대응보다 소폭 리밸런싱이 적합합니다."
                );
            }
            if (trendScore < 45 || ma200Dev > 90) {
                return new RegimeDecision(
                        "CROWDED_RUSH",
                        "적극 익절 후보",
                        "과밀 군중 밀집",
                        0.30,
                        "추세 품질이 약한 Rush라 과밀 리스크를 크게 반영합니다."
                );
            }
            return new RegimeDecision(
                    "NORMAL_RUSH",
                    "일부 익절 후보",
                    "군중 밀집",
                    0.15,
                    "Rush 구간이지만 추세가 완전히 훼손되지는 않아 일부 익절만 제안합니다."
            );
        }

        if (score >= DRIFT_LOWER) {
            if (trendScore >= 75) {
                return new RegimeDecision(
                        "HEALTHY_DRIFT",
                        "보유 우선",
                        "건강한 군중 쏠림",
                        0.02,
                        "강한 추세의 Drift라 성급한 익절보다 보유를 우선합니다."
                );
            }
            return new RegimeDecision(
                    "NORMAL_DRIFT",
                    "소폭 익절 후보",
                    "군중 쏠림",
                    0.06,
                    "군중 쏠림 구간으로 포트폴리오 비중을 가볍게 점검합니다."
            );
        }

        if (score <= FLEE_THRESHOLD) {
            if (trendScore >= 55) {
                return new RegimeDecision(
                        "OPPORTUNITY_FLEE",
                        "적극 추가매수 후보",
                        "기회형 군중 이탈",
                        0.22,
                        "군중 이탈이지만 장기 추세 품질이 유지돼 추가매수 후보로 봅니다."
                );
            }
            if (trendScore < 35) {
                return new RegimeDecision(
                        "BROKEN_FLEE",
                        "하락 훼손 관찰",
                        "훼손형 군중 이탈",
                        0.00,
                        "낮은 HERD와 약한 추세가 겹쳐 매수보다 관찰을 우선합니다."
                );
            }
            return new RegimeDecision(
                    "NORMAL_FLEE",
                    "소액 분할매수 후보",
                    "군중 이탈",
                    0.08,
                    "Flee 구간이지만 추세 확인이 더 필요해 소액 분할매수만 제안합니다."
            );
        }

        if (score <= SCATTER_UPPER) {
            if (trendScore >= 60) {
                return new RegimeDecision(
                        "OPPORTUNITY_SCATTER",
                        "분할 추가매수 후보",
                        "기회형 군중 흩어짐",
                        0.04,
                        "군중 흩어짐 구간에서 장기 추세가 유지돼 분할매수 후보입니다."
                );
            }
            return new RegimeDecision(
                    "NORMAL_SCATTER",
                    "관찰 우선",
                    "군중 흩어짐",
                    0.00,
                    "Scatter 구간이지만 추세 품질이 충분하지 않아 관찰을 우선합니다."
            );
        }

        return new RegimeDecision(
                "CALM",
                "보유 유지",
                "군중 균형",
                0.00,
                "HERD가 중립 구간이라 과도한 매매를 피합니다."
        );
    }

    private int calculateActionScore(
            double herdScore,
            int dataQuality,
            int trendScore,
            RegimeDecision regime
    ) {
        double signalStrength;
        if (herdScore <= SCATTER_UPPER) {
            signalStrength = herdScore <= FLEE_THRESHOLD
                    ? 60.0 + ((FLEE_THRESHOLD - herdScore) / FLEE_THRESHOLD) * 40.0
                    : 40.0 + ((SCATTER_UPPER - herdScore) / (SCATTER_UPPER - FLEE_THRESHOLD)) * 30.0;
            signalStrength = signalStrength * 0.45 + trendScore * 0.35 + dataQuality * 0.20;
        } else if (herdScore >= DRIFT_LOWER) {
            signalStrength = herdScore >= RUSH_THRESHOLD
                    ? 60.0 + ((herdScore - RUSH_THRESHOLD) / (100.0 - RUSH_THRESHOLD)) * 40.0
                    : 40.0 + ((herdScore - DRIFT_LOWER) / (RUSH_THRESHOLD - DRIFT_LOWER)) * 30.0;
            double crowdRisk = signalStrength * ("HEALTHY_RUSH".equals(regime.code()) ? 0.65 : 1.0);
            signalStrength = crowdRisk * 0.45 + (100 - trendScore) * 0.30 + dataQuality * 0.25;
        } else {
            signalStrength = 25.0 + dataQuality * 0.20;
        }

        if (regime.ratio() == 0.0) {
            signalStrength = Math.min(signalStrength, 45.0);
        }

        return clamp((int) Math.round(signalStrength), 0, 100);
    }

    private String actionGrade(int score, double ratio) {
        if (ratio == 0.0) return score >= 40 ? "WATCH" : "NO_ACTION";
        if (score >= 80) return "STRONG_ACTION";
        if (score >= 60) return "ACTION";
        if (score >= 40) return "WATCH";
        return "NO_ACTION";
    }

    private String displayStage(String herdStage) {
        if (herdStage == null || herdStage.isBlank()) return "Calm";
        return herdStage.startsWith("Herd ") ? herdStage.substring(5) : herdStage;
    }

    private int clamp(int value, int min, int max) {
        return Math.max(min, Math.min(max, value));
    }

    private record TrendContext(int score, double ma200Deviation, List<String> warnings) {
    }

    private record RegimeDecision(
            String code,
            String label,
            String regimeLabel,
            double ratio,
            String reason
    ) {
    }
}
