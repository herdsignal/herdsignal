package com.herdsignal.service;

import com.herdsignal.domain.HerdIndicator;
import com.herdsignal.domain.HerdScore;
import com.herdsignal.domain.InvestorProfile;
import com.herdsignal.dto.ActionDecision;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
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
    private static final String ACTION_MODEL_VERSION = "HERD_v6.1";
    private static final String ACTION_MODEL_NAME = "Validated Progressive Action Layer";
    private static final String BASE_MODEL_VERSION = "HERD_v4";
    private static final String ACTION_MODEL_STATUS = "RESEARCH_VALIDATION";
    private final PersonalActionTranslator personalActionTranslator;
    private final HerdTrendQualityCalculator trendCalculator;
    private final HerdMomentumCalculator momentumCalculator;
    private final HerdLifecycleClassifier lifecycleClassifier;
    private final PortfolioAdjustmentPolicy portfolioPolicy;
    private final ActionCooldownPolicy cooldownPolicy;
    private final boolean liveActionsEnabled;

    @Autowired
    public ActionDecisionService(
            PersonalActionTranslator personalActionTranslator,
            @Value("${herdsignal.action.live-enabled:false}") boolean liveActionsEnabled,
            @Value("${herdsignal.shadow.holdout-passed:false}") boolean holdoutPassed,
            @Value("${herdsignal.shadow.candidate-id:}") String candidateId,
            OperationalPromotionGate promotionGate
    ) {
        this.personalActionTranslator = personalActionTranslator;
        this.trendCalculator = new HerdTrendQualityCalculator();
        this.momentumCalculator = new HerdMomentumCalculator();
        this.lifecycleClassifier = new HerdLifecycleClassifier();
        this.portfolioPolicy = new PortfolioAdjustmentPolicy();
        this.cooldownPolicy = new ActionCooldownPolicy();
        this.liveActionsEnabled = liveActionsEnabled
                && holdoutPassed
                && promotionGate.isApproved(candidateId);
    }

    ActionDecisionService() {
        this(new PersonalActionTranslator(), false, false, "", ignored -> false);
    }

    ActionDecisionService(boolean liveActionsEnabled) {
        this(
                new PersonalActionTranslator(),
                liveActionsEnabled,
                liveActionsEnabled,
                "TEST_CANDIDATE",
                ignored -> liveActionsEnabled
        );
    }

    public ActionDecision decide(HerdScore score, HerdIndicator indicator, Integer qualityScore) {
        return decide(score, indicator, qualityScore, List.of());
    }

    public ActionDecision decide(
            HerdScore score,
            HerdIndicator indicator,
            Integer qualityScore,
            List<HerdScore> history
    ) {
        return decide(score, indicator, qualityScore, history, null, true);
    }

    public ActionDecision decide(
            HerdScore score,
            HerdIndicator indicator,
            Integer qualityScore,
            List<HerdScore> history,
            InvestorProfile profile,
            boolean currentlyHeld
    ) {
        return decide(
                score, indicator, qualityScore, history, profile, currentlyHeld,
                ActionCooldownContext.none(), PortfolioActionContext.unavailable());
    }

    public ActionDecision decide(
            HerdScore score,
            HerdIndicator indicator,
            Integer qualityScore,
            List<HerdScore> history,
            InvestorProfile profile,
            boolean currentlyHeld,
            ActionCooldownContext cooldownContext
    ) {
        return decide(
                score, indicator, qualityScore, history, profile, currentlyHeld,
                cooldownContext, PortfolioActionContext.unavailable());
    }

    public ActionDecision decide(
            HerdScore score,
            HerdIndicator indicator,
            Integer qualityScore,
            List<HerdScore> history,
            InvestorProfile profile,
            boolean currentlyHeld,
            ActionCooldownContext cooldownContext,
            PortfolioActionContext portfolioContext
    ) {
        double rawHerdScore = score.getHerdScore().doubleValue();
        int dataQuality = qualityScore != null ? qualityScore : 50;
        HerdTrendQualityCalculator.Result trend = trendCalculator.calculate(indicator);
        HerdMomentumCalculator.Result momentum = momentumCalculator.calculate(score, history);
        ScoreContext stabilized = stabilizeScore(rawHerdScore, score.getScoreDate(), history);
        double herdScore = stabilized.score();
        RegimeDecision regime = chooseRegime(herdScore, trend, momentum);
        HerdLifecycleClassifier.Result lifecycle = lifecycleClassifier.classify(score, history);
        RegimeDecision adjustedRegime = applyLifecycle(regime, lifecycle, herdScore);
        adjustedRegime = applyConfidence(adjustedRegime, dataQuality, momentum);
        PersonalActionTranslator.Translation personal = personalActionTranslator.translate(
                adjustedRegime.ratio(), adjustedRegime.label(), profile, currentlyHeld, herdScore);
        adjustedRegime = new RegimeDecision(
                adjustedRegime.code(),
                personal.label(),
                adjustedRegime.regimeLabel(),
                personal.ratio(),
                adjustedRegime.reason()
        );
        PortfolioAdjustment portfolioAdjustment = portfolioPolicy.adjust(
                adjustedRegime,
                portfolioContext == null ? PortfolioActionContext.unavailable() : portfolioContext,
                profile,
                herdScore
        );
        adjustedRegime = portfolioAdjustment.regime();
        CooldownAdjustment cooldownAdjustment = cooldownPolicy.apply(
                adjustedRegime,
                cooldownContext == null ? ActionCooldownContext.none() : cooldownContext,
                herdScore
        );
        adjustedRegime = cooldownAdjustment.regime();
        int actionScore = calculateActionScore(herdScore, dataQuality, trend.score(), momentum.score(), adjustedRegime);
        actionScore = clamp(actionScore + lifecycle.scoreAdjustment(), 0, 100);
        RegimeDecision researchRegime = adjustedRegime;
        adjustedRegime = applyOperationalGate(adjustedRegime);

        List<String> reasons = new ArrayList<>();
        reasons.add("HERD " + displayStage(score.getHerdStage()) + " 구간");
        reasons.add("장기 추세 품질 " + trend.score() + "/100");
        reasons.add(momentum.reason());
        reasons.add(stabilized.reason());
        reasons.add(lifecycle.reason());
        reasons.add("데이터 품질 " + dataQuality + "/100");
        reasons.add(adjustedRegime.reason());
        reasons.add(personal.reason());
        if (portfolioAdjustment.reason() != null) {
            reasons.add(portfolioAdjustment.reason());
        }
        if (cooldownAdjustment.reason() != null) {
            reasons.add(cooldownAdjustment.reason());
        }

        List<String> warnings = new ArrayList<>(trend.warnings());
        warnings.addAll(momentum.warnings());
        warnings.addAll(lifecycle.warnings());
        warnings.addAll(personal.warnings());
        warnings.addAll(portfolioAdjustment.warnings());
        warnings.addAll(cooldownAdjustment.warnings());
        if (dataQuality < 65) {
            warnings.add("데이터 품질이 낮아 행동 비율을 보수적으로 해석해야 합니다.");
        }
        if (adjustedRegime.ratio() == 0.0 && ("Flee".equals(displayStage(score.getHerdStage()))
                || "Scatter".equals(displayStage(score.getHerdStage())))) {
            warnings.add("낮은 HERD 점수지만 추세 훼손 가능성이 있어 관찰을 우선합니다.");
        }

        return ActionDecision.builder()
                .actionModelVersion(ACTION_MODEL_VERSION)
                .actionModelName(ACTION_MODEL_NAME)
                .baseModelVersion(BASE_MODEL_VERSION)
                .actionModelStatus(ACTION_MODEL_STATUS)
                .investorStrategy(personal.strategy())
                .investorStrategyLabel(personal.strategyLabel())
                .actionScore(actionScore)
                .actionGrade(actionGrade(actionScore, adjustedRegime.ratio()))
                .actionLabel(adjustedRegime.label())
                .actionRatio(BigDecimal.valueOf(adjustedRegime.ratio()).setScale(2, RoundingMode.HALF_UP))
                .researchActionRatio(BigDecimal.valueOf(researchRegime.ratio()).setScale(2, RoundingMode.HALF_UP))
                .researchActionLabel(researchRegime.label())
                .actionRegime(adjustedRegime.code())
                .actionRegimeLabel(adjustedRegime.regimeLabel())
                .actionReasons(reasons)
                .actionWarnings(warnings)
                .actionCooldownActive(cooldownAdjustment.cooldown().active())
                .actionCooldownRemainingDays(cooldownAdjustment.cooldown().remainingTradingDays())
                .lastActionDate(cooldownAdjustment.cooldown().lastActionDate())
                .currentTickerWeight(ratioValue(
                        portfolioAdjustment.context(), portfolioAdjustment.context().currentTickerWeight()))
                .currentEquityRatio(ratioValue(
                        portfolioAdjustment.context(), portfolioAdjustment.context().currentEquityRatio()))
                .targetEquityRatio(ratioValue(
                        portfolioAdjustment.context(), portfolioAdjustment.context().targetEquityRatio()))
                .actionIntensity(actionIntensity(adjustedRegime.ratio()).code())
                .actionIntensityLabel(actionIntensity(adjustedRegime.ratio()).label())
                .build();
    }

    private RegimeDecision applyOperationalGate(RegimeDecision regime) {
        if (liveActionsEnabled || regime.ratio() == 0.0) {
            return regime;
        }
        return new RegimeDecision(
                regime.code() + "_RESEARCH_ONLY",
                "연구 검증 중·관찰",
                regime.regimeLabel(),
                0.0,
                regime.reason() + " 운영 채택 기준을 통과하지 않아 실행 비율을 0%로 제한합니다."
        );
    }

    private ActionIntensity actionIntensity(double ratio) {
        if (ratio <= 0.0) return new ActionIntensity("NONE", "관찰");
        if (ratio <= 0.05) return new ActionIntensity("LOW", "낮음");
        if (ratio <= 0.15) return new ActionIntensity("MEDIUM", "중간");
        return new ActionIntensity("HIGH", "높음");
    }

    private BigDecimal ratioValue(PortfolioActionContext context, double value) {
        return context.available()
                ? BigDecimal.valueOf(value).setScale(4, RoundingMode.HALF_UP)
                : null;
    }

    /** 경계 ±2pt에서는 직전 구간을 유지해 하루 단위 신호 뒤집힘을 줄인다. */
    private ScoreContext stabilizeScore(double current, LocalDate latestDate, List<HerdScore> history) {
        HerdScore previous = previousScore(history, latestDate);
        if (previous == null || previous.getHerdScore() == null) {
            return new ScoreContext(current, "단계 안정화 비교 이력 부족");
        }
        double before = previous.getHerdScore().doubleValue();
        double[] boundaries = {FLEE_THRESHOLD, SCATTER_UPPER, DRIFT_LOWER, RUSH_THRESHOLD};
        for (double boundary : boundaries) {
            if (Math.abs(current - boundary) <= 2.0 && (current - boundary) * (before - boundary) < 0) {
                double stable = before < boundary ? boundary - 0.01 : boundary + 0.01;
                return new ScoreContext(stable, String.format("경계 안정화 적용 %.1f→%.1f", before, current));
            }
        }
        return new ScoreContext(current, "단계 안정화 변동 없음");
    }

    /** 데이터와 변화 이력이 약할수록 행동 비율만 축소하고 시장 상태 자체는 보존한다. */
    private RegimeDecision applyConfidence(RegimeDecision regime, int dataQuality, HerdMomentumCalculator.Result momentum) {
        if (regime.ratio() == 0.0) return regime;
        double qualityFactor = dataQuality >= 85 ? 1.0 : dataQuality >= 65 ? 0.85 : dataQuality >= 50 ? 0.65 : 0.40;
        double historyFactor = momentum.observations() >= 20 ? 1.0 : momentum.observations() >= 5 ? 0.85 : 0.65;
        double ratio = BigDecimal.valueOf(regime.ratio() * qualityFactor * historyFactor)
                .setScale(2, RoundingMode.HALF_UP).doubleValue();
        return new RegimeDecision(regime.code(), regime.label(), regime.regimeLabel(), ratio,
                regime.reason() + String.format(" 신뢰도 보정 %.0f%%를 적용합니다.", qualityFactor * historyFactor * 100));
    }

    private RegimeDecision applyLifecycle(RegimeDecision regime, HerdLifecycleClassifier.Result lifecycle, double herdScore) {
        if (regime.ratio() == 0.0) {
            return regime;
        }

        double adjustedRatio = BigDecimal.valueOf(regime.ratio() * lifecycle.ratioMultiplier())
                .setScale(2, RoundingMode.HALF_UP)
                .doubleValue();

        if (lifecycle.signalDays() <= 5 && adjustedRatio > 0.0) {
            return new RegimeDecision(
                    regime.code() + "_FRESH",
                    freshLabel(regime.label(), herdScore),
                    regime.regimeLabel(),
                    adjustedRatio,
                    regime.reason() + " 단, 신호 초입이라 첫 행동 비율을 낮춥니다."
            );
        }

        if (lifecycle.signalDays() > 45 && adjustedRatio > 0.0) {
            return new RegimeDecision(
                    regime.code() + "_EXTENDED",
                    extendedLabel(regime.label(), herdScore),
                    regime.regimeLabel(),
                    adjustedRatio,
                    regime.reason() + " 다만 오래 지속된 신호라 추격 비중을 제한합니다."
            );
        }

        return new RegimeDecision(
                regime.code(),
                regime.label(),
                regime.regimeLabel(),
                adjustedRatio,
                regime.reason()
        );
    }

    private String freshLabel(String label, double herdScore) {
        if (herdScore <= SCATTER_UPPER) {
            return label.replace("적극 ", "").replace("후보", "확인");
        }
        if (herdScore >= DRIFT_LOWER) {
            return label.replace("적극 ", "").replace("후보", "확인");
        }
        return label;
    }

    private String extendedLabel(String label, double herdScore) {
        if (herdScore <= SCATTER_UPPER) {
            return "추격매수 보류";
        }
        if (herdScore >= DRIFT_LOWER) {
            return "분할 익절 유지";
        }
        return label;
    }

    private HerdScore previousScore(List<HerdScore> history, LocalDate latestDate) {
        if (history == null) return null;
        return history.stream().filter(row -> row.getScoreDate() != null && row.getHerdScore() != null
                        && (latestDate == null || row.getScoreDate().isBefore(latestDate)))
                .max((a, b) -> a.getScoreDate().compareTo(b.getScoreDate())).orElse(null);
    }

    private RegimeDecision chooseRegime(double score, HerdTrendQualityCalculator.Result trend, HerdMomentumCalculator.Result momentum) {
        int trendScore = trend.score();
        double ma200Dev = trend.ma200Deviation();
        boolean momentumRising = momentum.monthDelta() >= 5.0;
        boolean momentumCooling = momentum.monthDelta() <= -3.0 || momentum.shortDelta() <= -3.0;

        if (score >= RUSH_THRESHOLD) {
            if (score >= 90.0) {
                if (momentumCooling || trendScore < 55 || ma200Dev > 90) {
                    return new RegimeDecision(
                            "PEAKING_RUSH",
                            "적극 익절 후보",
                            "정점권 군중 밀집",
                            0.30,
                            "Rush 심화 후 HERD 둔화 또는 추세 부담이 보여 익절 강도를 높입니다."
                    );
                }
                return new RegimeDecision(
                        "EXTENDING_RUSH",
                        "분할 익절 후보",
                        "확장형 군중 밀집",
                        0.18,
                        "HERD가 90 이상이지만 과열이 진행 중이라 전량 대응보다 분할 익절을 우선합니다."
                );
            }
            if (score >= 85.0) {
                return new RegimeDecision(
                        momentumCooling ? "COOLING_RUSH" : "DEEP_RUSH",
                        momentumCooling ? "익절 우선 후보" : "일부 익절 후보",
                        momentumCooling ? "둔화형 군중 밀집" : "심화형 군중 밀집",
                        momentumCooling ? 0.22 : 0.12,
                        momentumCooling
                                ? "Rush 구간에서 HERD 둔화가 시작돼 익절 비중을 높입니다."
                                : "Rush가 심화 중이지만 추세가 이어져 일부 익절만 제안합니다."
                );
            }
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
                    momentumRising ? 0.08 : 0.15,
                    momentumRising
                            ? "Rush 초입에서 HERD가 상승 중이라 익절은 작게 나눕니다."
                            : "Rush 구간이지만 추세가 완전히 훼손되지는 않아 일부 익절만 제안합니다."
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
            if (score <= 10.0) {
                if (trendScore < 35 && !momentumRising) {
                    return new RegimeDecision(
                            "BROKEN_DEEP_FLEE",
                            "하락 훼손 관찰",
                            "깊은 군중 이탈",
                            0.00,
                            "Flee가 깊지만 추세와 HERD 변화가 모두 약해 매수보다 관찰을 우선합니다."
                    );
                }
                return new RegimeDecision(
                        momentumRising ? "REVERSING_DEEP_FLEE" : "DEEP_FLEE",
                        momentumRising ? "적극 추가매수 후보" : "분할매수 후보",
                        momentumRising ? "반등형 군중 이탈" : "심화형 군중 이탈",
                        momentumRising ? 0.30 : 0.15,
                        momentumRising
                                ? "깊은 Flee 이후 HERD가 되돌아와 추가매수 강도를 높입니다."
                                : "깊은 Flee지만 아직 반등 확인 전이라 분할매수로 제한합니다."
                );
            }
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
            if (score <= 25.0 && trendScore >= 60 && momentumRising) {
                return new RegimeDecision(
                        "REVERSING_SCATTER",
                        "분할 추가매수 후보",
                        "회복형 군중 흩어짐",
                        0.08,
                        "Scatter 저점권에서 HERD 회복이 보여 분할매수 후보로 봅니다."
                );
            }
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
            int momentumScore,
            RegimeDecision regime
    ) {
        double signalStrength;
        if (herdScore <= SCATTER_UPPER) {
            signalStrength = herdScore <= FLEE_THRESHOLD
                    ? 60.0 + ((FLEE_THRESHOLD - herdScore) / FLEE_THRESHOLD) * 40.0
                    : 40.0 + ((SCATTER_UPPER - herdScore) / (SCATTER_UPPER - FLEE_THRESHOLD)) * 30.0;
            signalStrength = signalStrength * 0.40 + trendScore * 0.30 + momentumScore * 0.15 + dataQuality * 0.15;
        } else if (herdScore >= DRIFT_LOWER) {
            signalStrength = herdScore >= RUSH_THRESHOLD
                    ? 60.0 + ((herdScore - RUSH_THRESHOLD) / (100.0 - RUSH_THRESHOLD)) * 40.0
                    : 40.0 + ((herdScore - DRIFT_LOWER) / (RUSH_THRESHOLD - DRIFT_LOWER)) * 30.0;
            double crowdRisk = signalStrength * ("HEALTHY_RUSH".equals(regime.code()) ? 0.65 : 1.0);
            signalStrength = crowdRisk * 0.42 + (100 - trendScore) * 0.25 + (100 - momentumScore) * 0.18 + dataQuality * 0.15;
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

    private record ScoreContext(double score, String reason) {
    }

    record RegimeDecision(
            String code,
            String label,
            String regimeLabel,
            double ratio,
            String reason
    ) {
    }

    record CooldownAdjustment(
            RegimeDecision regime,
            ActionCooldownContext.Cooldown cooldown,
            String reason,
            List<String> warnings
    ) {
    }

    record PortfolioAdjustment(
            RegimeDecision regime,
            PortfolioActionContext context,
            String reason,
            List<String> warnings
    ) {
    }

    private record ActionIntensity(String code, String label) {
    }
}
