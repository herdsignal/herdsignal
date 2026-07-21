package com.herdsignal.service;

import com.herdsignal.domain.HerdScore;
import com.herdsignal.domain.InvestorProfile;
import com.herdsignal.dto.ActionDecision;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class ActionDecisionServiceTest {

    private final ActionDecisionService service = new ActionDecisionService(true);

    @ParameterizedTest
    @CsvSource({
            "10,DEEP_FLEE_FRESH",
            "15,NORMAL_FLEE_FRESH",
            "16,NORMAL_SCATTER",
            "40,NORMAL_SCATTER",
            "41,CALM",
            "59,CALM",
            "60,PROFIT_TAKE_EVIDENCE_BLOCKED",
            "74,PROFIT_TAKE_EVIDENCE_BLOCKED",
            "75,PROFIT_TAKE_EVIDENCE_BLOCKED",
            "90,PROFIT_TAKE_EVIDENCE_BLOCKED"
    })
    void preservesFiveStageAndInternalRegimeBoundaries(double herd, String expectedRegime) {
        HerdScore latest = score(LocalDate.of(2026, 7, 10), herd, stageFor(herd), "HOLD");

        ActionDecision decision = service.decide(latest, null, 90, List.of());

        assertThat(decision.getActionRegime()).isEqualTo(expectedRegime);
    }

    @Test
    void disablesUnvalidatedActionsByDefaultButPreservesResearchOutput() {
        ActionDecisionService gatedService = new ActionDecisionService();
        HerdScore latest = score(LocalDate.of(2026, 7, 10), 8, "Flee", "BUY");

        ActionDecision decision = gatedService.decide(
                latest, null, 90,
                historyUntil(latest.getScoreDate(), 25, 18, "Flee", "BUY"),
                profile("NEW_ENTRY", "GROWTH", 10, 6, "0.30"),
                false
        );

        assertThat(decision.getActionRatio()).isZero();
        assertThat(decision.getActionLabel()).isEqualTo("연구 검증 중·관찰");
        assertThat(decision.getActionRegime()).endsWith("_RESEARCH_ONLY");
        assertThat(decision.getResearchActionRatio()).isPositive();
        assertThat(decision.getResearchActionLabel()).contains("진입");
    }

    @Test
    void scalesActionRatioDownWhenDataQualityIsLow() {
        HerdScore latest = score(LocalDate.of(2026, 7, 10), 12, "Flee", "BUY");
        List<HerdScore> history = historyUntil(latest.getScoreDate(), 25, 18, "Flee", "BUY");

        ActionDecision highQuality = service.decide(latest, null, 90, history);
        ActionDecision lowQuality = service.decide(latest, null, 40, history);

        assertThat(highQuality.getActionModelVersion()).isEqualTo("HERD_v6.1");
        assertThat(highQuality.getActionModelStatus()).isEqualTo("RESEARCH_VALIDATION");
        assertThat(highQuality.getActionIntensity()).isIn("LOW", "MEDIUM", "HIGH");
        assertThat(lowQuality.getActionRatio()).isLessThan(highQuality.getActionRatio());
    }

    @Test
    void keepsPreviousStageInsideBoundaryBuffer() {
        LocalDate latestDate = LocalDate.of(2026, 7, 10);
        HerdScore latest = score(latestDate, 41, "Calm", "HOLD");
        List<HerdScore> history = List.of(score(latestDate.minusDays(1), 39, "Scatter", "ADD"));

        ActionDecision decision = service.decide(latest, null, 90, history);

        assertThat(decision.getActionRegime()).isEqualTo("NORMAL_SCATTER");
        assertThat(decision.getActionReasons()).anyMatch(reason -> reason.contains("경계 안정화 적용"));
    }

    @Test
    void blocksBuyWhenLiquidityBufferIsTooLow() {
        HerdScore latest = score(LocalDate.of(2026, 7, 10), 12, "Flee", "BUY");
        InvestorProfile profile = profile("NEW_ENTRY", "GROWTH", 10, 2, "0.30");

        ActionDecision decision = service.decide(
                latest, null, 90, historyUntil(latest.getScoreDate(), 25, 18, "Flee", "BUY"),
                profile, false);

        assertThat(decision.getActionRatio()).isZero();
        assertThat(decision.getActionLabel()).isEqualTo("현금 여유 확보 우선");
        assertThat(decision.getActionWarnings()).anyMatch(warning -> warning.contains("생활비 여유"));
    }

    @Test
    void givesDifferentCapsForNewEntryAndMonthlyDca() {
        HerdScore latest = score(LocalDate.of(2026, 7, 10), 8, "Flee", "BUY");
        List<HerdScore> history = historyUntil(latest.getScoreDate(), 25, 18, "Flee", "BUY");

        ActionDecision entry = service.decide(
                latest, null, 90, history, profile("NEW_ENTRY", "GROWTH", 10, 6, "0.30"), false);
        ActionDecision dca = service.decide(
                latest, null, 90, history, profile("MONTHLY_DCA", "GROWTH", 10, 6, "0.30"), true);

        assertThat(entry.getActionRatio()).isEqualByComparingTo("0.10");
        assertThat(dca.getActionRatio()).isEqualByComparingTo("0.05");
        assertThat(entry.getInvestorStrategyLabel()).isEqualTo("신규 진입자");
        assertThat(dca.getActionLabel()).isEqualTo("정기 적립 우선");
    }

    @Test
    void explainsTargetWeightForRebalancingProfile() {
        HerdScore latest = score(LocalDate.of(2026, 7, 10), 80, "Rush", "SELL");
        InvestorProfile profile = profile("TARGET_REBALANCE", "BALANCED", 10, 6, "0.15");

        ActionDecision decision = service.decide(latest, null, 90, List.of(), profile, true);

        assertThat(decision.getActionLabel()).isEqualTo("익절 근거 미채택");
        assertThat(decision.getActionWarnings()).anyMatch(warning -> warning.contains("목표 70%"));
    }

    @Test
    void blocksRepeatedBuyDuringCooldown() {
        HerdScore latest = score(LocalDate.of(2026, 7, 10), 8, "Flee", "BUY");
        ActionCooldownContext cooldown = new ActionCooldownContext(
                new ActionCooldownContext.Cooldown(
                        true, 6, 14, LocalDate.of(2026, 7, 2)),
                ActionCooldownContext.Cooldown.none()
        );

        ActionDecision decision = service.decide(
                latest,
                null,
                90,
                historyUntil(latest.getScoreDate(), 25, 18, "Flee", "BUY"),
                profile("EXISTING_HOLDER", "GROWTH", 10, 6, "0.30"),
                true,
                cooldown
        );

        assertThat(decision.getActionRatio()).isZero();
        assertThat(decision.getActionRegime()).endsWith("_COOLDOWN");
        assertThat(decision.getActionCooldownActive()).isTrue();
        assertThat(decision.getActionCooldownRemainingDays()).isEqualTo(14);
        assertThat(decision.getLastActionDate()).isEqualTo(LocalDate.of(2026, 7, 2));
        assertThat(decision.getActionWarnings()).anyMatch(warning -> warning.contains("반복 행동"));
    }

    @Test
    void unadmittedProfitTakeIsBlockedEvenWhenLiveActionsAreEnabled() {
        HerdScore latest = score(LocalDate.of(2026, 7, 10), 88, "Rush", "SELL");
        ActionCooldownContext cooldown = new ActionCooldownContext(
                new ActionCooldownContext.Cooldown(
                        true, 6, 14, LocalDate.of(2026, 7, 2)),
                ActionCooldownContext.Cooldown.none()
        );

        ActionDecision decision = service.decide(
                latest,
                null,
                90,
                List.of(),
                profile("EXISTING_HOLDER", "GROWTH", 10, 6, "0.30"),
                true,
                cooldown
        );

        assertThat(decision.getActionRatio()).isZero();
        assertThat(decision.getResearchActionRatio()).isZero();
        assertThat(decision.getActionRegime()).isEqualTo("PROFIT_TAKE_EVIDENCE_BLOCKED");
        assertThat(decision.getActionCooldownActive()).isFalse();
    }

    @Test
    void separatesConcentrationRiskRebalanceFromPredictiveProfitTake() {
        HerdScore latest = score(LocalDate.of(2026, 7, 10), 8, "Flee", "BUY");
        PortfolioActionContext portfolio = new PortfolioActionContext(
                true, 0.28, 0.65, 0.70);

        ActionDecision decision = service.decide(
                latest,
                null,
                90,
                historyUntil(latest.getScoreDate(), 25, 18, "Flee", "BUY"),
                profile("EXISTING_HOLDER", "GROWTH", 10, 6, "0.30"),
                true,
                ActionCooldownContext.none(),
                portfolio
        );

        assertThat(decision.getActionRatio()).isEqualByComparingTo("0.05");
        assertThat(decision.getActionLabel()).isEqualTo("집중도 리밸런싱 후보");
        assertThat(decision.getActionRegime()).isEqualTo("RISK_REBALANCE_CONCENTRATION");
        assertThat(decision.getActionWarnings()).anyMatch(warning -> warning.contains("집중 위험 관리"));
        assertThat(decision.getCurrentTickerWeight()).isEqualByComparingTo("0.2800");
    }

    @Test
    void reducesBuyStrengthWhenTickerWeightExceedsFifteenPercent() {
        HerdScore latest = score(LocalDate.of(2026, 7, 10), 8, "Flee", "BUY");
        List<HerdScore> history = historyUntil(latest.getScoreDate(), 25, 18, "Flee", "BUY");
        InvestorProfile profile = profile("EXISTING_HOLDER", "GROWTH", 10, 6, "0.30");

        ActionDecision withoutPortfolio = service.decide(
                latest, null, 90, history, profile, true);
        ActionDecision concentrated = service.decide(
                latest, null, 90, history, profile, true,
                ActionCooldownContext.none(),
                new PortfolioActionContext(true, 0.18, 0.60, 0.70));

        assertThat(concentrated.getActionRatio()).isLessThan(withoutPortfolio.getActionRatio());
        assertThat(concentrated.getActionWarnings()).anyMatch(warning -> warning.contains("15%"));
    }

    private static InvestorProfile profile(
            String strategy, String risk, int horizon, int liquidity, String maxRatio) {
        return InvestorProfile.builder()
                .userId("local").strategy(strategy).riskTolerance(risk)
                .timeHorizonYears(horizon).liquidityBufferMonths(liquidity)
                .maxActionRatio(new BigDecimal(maxRatio)).targetEquityRatio(new BigDecimal("0.70"))
                .build();
    }

    private static List<HerdScore> historyUntil(LocalDate latest, int count, double start, String stage, String signal) {
        List<HerdScore> rows = new ArrayList<>();
        for (int i = count; i >= 1; i--) {
            rows.add(score(latest.minusDays(i), start - i * 0.1, stage, signal));
        }
        return rows;
    }

    private static HerdScore score(LocalDate date, double value, String stage, String signal) {
        return HerdScore.builder()
                .ticker("TEST")
                .scoreDate(date)
                .herdScore(BigDecimal.valueOf(value))
                .herdStage(stage)
                .signal(signal)
                .build();
    }

    private static String stageFor(double score) {
        if (score <= 15) return "Flee";
        if (score <= 40) return "Scatter";
        if (score < 60) return "Calm";
        if (score < 75) return "Drift";
        return "Rush";
    }
}
