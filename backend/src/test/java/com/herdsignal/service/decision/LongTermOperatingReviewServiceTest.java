package com.herdsignal.service.decision;

import com.herdsignal.domain.InvestorProfile;
import com.herdsignal.service.CurrentUserService;
import com.herdsignal.service.InvestorProfileService;
import com.herdsignal.service.PortfolioActionContext;
import com.herdsignal.service.PortfolioActionContextService;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class LongTermOperatingReviewServiceTest {

    @Test
    void addsPortfolioFactsButKeepsOperationalActionLocked() {
        ObjectiveEvidenceService objectiveService = mock(ObjectiveEvidenceService.class);
        CurrentUserService currentUser = mock(CurrentUserService.class);
        InvestorProfileService profileService = mock(InvestorProfileService.class);
        PortfolioActionContextService portfolioService = mock(PortfolioActionContextService.class);
        InvestorProfile profile = profile();
        ObjectiveReviewResponse objective = objective(true);

        when(objectiveService.review("NVDA")).thenReturn(objective);
        when(currentUser.requireUserId()).thenReturn("user-1");
        when(profileService.forDecision("user-1")).thenReturn(profile);
        when(portfolioService.getContexts("user-1", List.of("NVDA"), profile))
                .thenReturn(Map.of("NVDA", new PortfolioActionContext(true, 0.20, 0.75, 0.70)));

        PersonalOperatingReviewResponse response = new LongTermOperatingReviewService(
                objectiveService, currentUser, profileService, portfolioService).review("NVDA");

        assertThat(response.status()).isEqualTo("OBSERVATION_ONLY");
        assertThat(response.portfolioFit().held()).isTrue();
        assertThat(response.portfolioFit().currentTickerWeight()).isEqualTo(0.20);
        assertThat(response.mandate().userMaximumActionRatio()).isEqualByComparingTo("0.15");
        assertThat(response.mandate().effectiveActionRatioCap()).isZero();
        assertThat(response.riskVeto().actionBlocked()).isTrue();
        assertThat(response.riskVeto().codes())
                .contains("BUSINESS_HEALTH_NOT_CONNECTED", "DIRECTIONAL_EVIDENCE_NOT_ADOPTED");
        assertThat(response.operationalAction()).isEqualTo("OBSERVE");
        assertThat(response.operationalActionRatio()).isZero();
    }

    @Test
    void blockedEvidenceGateRemainsInsufficientRegardlessOfPortfolio() {
        ObjectiveEvidenceService objectiveService = mock(ObjectiveEvidenceService.class);
        CurrentUserService currentUser = mock(CurrentUserService.class);
        InvestorProfileService profileService = mock(InvestorProfileService.class);
        PortfolioActionContextService portfolioService = mock(PortfolioActionContextService.class);
        InvestorProfile profile = profile();
        when(objectiveService.review("NVDA")).thenReturn(objective(false));
        when(currentUser.requireUserId()).thenReturn("user-1");
        when(profileService.forDecision("user-1")).thenReturn(profile);
        when(portfolioService.getContexts("user-1", List.of("NVDA"), profile)).thenReturn(Map.of());

        PersonalOperatingReviewResponse response = new LongTermOperatingReviewService(
                objectiveService, currentUser, profileService, portfolioService).review("NVDA");

        assertThat(response.status()).isEqualTo("INSUFFICIENT_DATA");
        assertThat(response.riskVeto().codes()).contains("DATA_GATE_BLOCKED");
        assertThat(response.operationalActionRatio()).isZero();
    }

    private ObjectiveReviewResponse objective(boolean gateOpen) {
        List<DecisionAreaAssessment> assessments = List.of(
                new DecisionAreaAssessment(DecisionArea.BUSINESS_HEALTH, AssessmentStatus.NO_VIEW,
                        "없음", List.of(), List.of()),
                new DecisionAreaAssessment(DecisionArea.INFORMATION_CHANGE, AssessmentStatus.NO_VIEW,
                        "없음", List.of(), List.of())
        );
        return new ObjectiveReviewResponse(
                gateOpen ? "AVAILABLE" : "INSUFFICIENT_DATA", "NVDA", null,
                new EvidenceGateResult(
                        gateOpen ? EvidenceGateResult.Status.OPEN : EvidenceGateResult.Status.BLOCKED,
                        gateOpen ? List.of() : List.of("STALE")),
                assessments, false, "OBSERVE", 0.0);
    }

    private InvestorProfile profile() {
        return InvestorProfile.builder()
                .userId("user-1")
                .strategy("EXISTING_HOLDER")
                .riskTolerance("BALANCED")
                .timeHorizonYears(10)
                .liquidityBufferMonths(6)
                .maxActionRatio(new BigDecimal("0.15"))
                .targetEquityRatio(new BigDecimal("0.70"))
                .rebalanceBudget(BigDecimal.ZERO)
                .cashTargetRatio(new BigDecimal("0.10"))
                .rebalanceMode("STANDARD")
                .build();
    }
}
