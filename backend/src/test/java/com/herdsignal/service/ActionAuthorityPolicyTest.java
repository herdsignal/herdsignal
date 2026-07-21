package com.herdsignal.service;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ActionAuthorityPolicyTest {
    private final ActionAuthorityPolicy policy = new ActionAuthorityPolicy();

    @Test
    void blocksHerdBasedProfitTakeWithoutIndependentEvidence() {
        var regime = new ActionDecisionService.RegimeDecision(
                "PEAKING_RUSH", "익절 후보", "Rush", 0.30, "과열");

        var result = policy.apply(regime, 92);

        assertThat(result.code()).isEqualTo("PROFIT_TAKE_EVIDENCE_BLOCKED");
        assertThat(result.ratio()).isZero();
    }

    @Test
    void preservesPortfolioRiskRebalanceAuthority() {
        var regime = new ActionDecisionService.RegimeDecision(
                "RISK_REBALANCE_CONCENTRATION", "집중도 리밸런싱 후보", "Calm", 0.05, "집중 위험");

        assertThat(policy.apply(regime, 50)).isEqualTo(regime);
    }
}
