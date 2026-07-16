package com.herdsignal.service;

import com.herdsignal.domain.HerdScore;
import com.herdsignal.domain.InvestorProfile;
import com.herdsignal.dto.ActionDecision;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class ActionDecisionServiceTest {

    private final ActionDecisionService service = new ActionDecisionService();

    @Test
    void scalesActionRatioDownWhenDataQualityIsLow() {
        HerdScore latest = score(LocalDate.of(2026, 7, 10), 12, "Flee", "BUY");
        List<HerdScore> history = historyUntil(latest.getScoreDate(), 25, 18, "Flee", "BUY");

        ActionDecision highQuality = service.decide(latest, null, 90, history);
        ActionDecision lowQuality = service.decide(latest, null, 40, history);

        assertThat(highQuality.getActionModelVersion()).isEqualTo("HERD_v6.1");
        assertThat(highQuality.getActionModelStatus()).isEqualTo("RESEARCH_VALIDATION");
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

        assertThat(decision.getActionLabel()).isEqualTo("목표 비중 확인");
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
    void buyCooldownDoesNotBlockSellDirection() {
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

        assertThat(decision.getActionRatio()).isPositive();
        assertThat(decision.getActionCooldownActive()).isFalse();
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
}
