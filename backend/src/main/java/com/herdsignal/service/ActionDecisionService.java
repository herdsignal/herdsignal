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
    private final HerdRegimePolicy regimePolicy;
    private final HerdScoreStabilizer scoreStabilizer;
    private final ActionStrengthCalculator strengthCalculator;
    private final ActionRatioAdjustmentPolicy ratioAdjustmentPolicy;
    private final ActionAuthorityPolicy authorityPolicy;
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
        this.regimePolicy = new HerdRegimePolicy();
        this.scoreStabilizer = new HerdScoreStabilizer();
        this.strengthCalculator = new ActionStrengthCalculator();
        this.ratioAdjustmentPolicy = new ActionRatioAdjustmentPolicy();
        this.authorityPolicy = new ActionAuthorityPolicy();
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
        HerdScoreStabilizer.Result stabilized = scoreStabilizer.stabilize(
                rawHerdScore, score.getScoreDate(), history);
        double herdScore = stabilized.score();
        RegimeDecision regime = regimePolicy.choose(herdScore, trend, momentum);
        HerdLifecycleClassifier.Result lifecycle = lifecycleClassifier.classify(score, history);
        RegimeDecision adjustedRegime = ratioAdjustmentPolicy.applyLifecycle(regime, lifecycle, herdScore);
        adjustedRegime = ratioAdjustmentPolicy.applyConfidence(adjustedRegime, dataQuality, momentum);
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
        adjustedRegime = authorityPolicy.apply(adjustedRegime, herdScore);
        CooldownAdjustment cooldownAdjustment = cooldownPolicy.apply(
                adjustedRegime,
                cooldownContext == null ? ActionCooldownContext.none() : cooldownContext,
                herdScore
        );
        adjustedRegime = cooldownAdjustment.regime();
        int actionScore = strengthCalculator.score(
                herdScore, dataQuality, trend.score(), momentum.score(), adjustedRegime);
        actionScore = Math.max(0, Math.min(100, actionScore + lifecycle.scoreAdjustment()));
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
                .actionGrade(strengthCalculator.grade(actionScore, adjustedRegime.ratio()))
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
                .actionIntensity(strengthCalculator.intensity(adjustedRegime.ratio()).code())
                .actionIntensityLabel(strengthCalculator.intensity(adjustedRegime.ratio()).label())
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

    private BigDecimal ratioValue(PortfolioActionContext context, double value) {
        return context.available()
                ? BigDecimal.valueOf(value).setScale(4, RoundingMode.HALF_UP)
                : null;
    }

    /** 데이터와 변화 이력이 약할수록 행동 비율만 축소하고 시장 상태 자체는 보존한다. */
    private String displayStage(String herdStage) {
        if (herdStage == null || herdStage.isBlank()) return "Calm";
        return herdStage.startsWith("Herd ") ? herdStage.substring(5) : herdStage;
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

}
