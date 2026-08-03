package com.herdsignal.service.decision;

import com.herdsignal.domain.InvestorProfile;
import com.herdsignal.service.CurrentUserService;
import com.herdsignal.service.InvestorProfileService;
import com.herdsignal.service.PortfolioActionContext;
import com.herdsignal.service.PortfolioActionContextService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

/** 객관적 관찰과 개인 맥락을 결합하되 행동 권한은 별도로 잠근다. */
@Service
public class LongTermOperatingReviewService {
    private final ObjectiveEvidenceService objectiveEvidenceService;
    private final CurrentUserService currentUserService;
    private final InvestorProfileService investorProfileService;
    private final PortfolioActionContextService portfolioActionContextService;
    private final DecisionSynthesisPolicy synthesisPolicy;
    private final OperatingActionAuthorizationGate actionAuthorizationGate;
    private final PortfolioFitCalculator portfolioFitCalculator = new PortfolioFitCalculator();
    private final IndependentRiskVetoPolicy riskVetoPolicy = new IndependentRiskVetoPolicy();

    @Autowired
    public LongTermOperatingReviewService(
            ObjectiveEvidenceService objectiveEvidenceService,
            CurrentUserService currentUserService,
            InvestorProfileService investorProfileService,
            PortfolioActionContextService portfolioActionContextService,
            DecisionSynthesisPolicy synthesisPolicy,
            OperatingActionAuthorizationGate actionAuthorizationGate
    ) {
        this.objectiveEvidenceService = objectiveEvidenceService;
        this.currentUserService = currentUserService;
        this.investorProfileService = investorProfileService;
        this.portfolioActionContextService = portfolioActionContextService;
        this.synthesisPolicy = synthesisPolicy;
        this.actionAuthorizationGate = actionAuthorizationGate;
    }

    LongTermOperatingReviewService(
            ObjectiveEvidenceService objectiveEvidenceService,
            CurrentUserService currentUserService,
            InvestorProfileService investorProfileService,
            PortfolioActionContextService portfolioActionContextService,
            DecisionSynthesisPolicy synthesisPolicy
    ) {
        this(objectiveEvidenceService, currentUserService, investorProfileService,
                portfolioActionContextService, synthesisPolicy,
                OperatingActionAuthorizationGate.failClosed());
    }

    public PersonalOperatingReviewResponse review(String ticker) {
        ObjectiveReviewResponse objective = objectiveEvidenceService.review(ticker);
        String userId = currentUserService.requireUserId();
        InvestorProfile profile = investorProfileService.forDecision(userId);
        PortfolioActionContext context = portfolioActionContextService.getContexts(
                        userId, List.of(objective.ticker()), profile)
                .getOrDefault(objective.ticker(), PortfolioActionContext.unavailable());
        PortfolioFitAssessment portfolioFit = portfolioFitCalculator.assess(context);
        RiskVeto veto = riskVetoPolicy.evaluate(objective, portfolioFit);
        DecisionSynthesis synthesis = actionAuthorizationGate.enforce(
                synthesisPolicy.synthesize(objective, portfolioFit, veto));

        return new PersonalOperatingReviewResponse(
                synthesis.decision().name(),
                objective.ticker(),
                objective,
                OperatingMandate.from(profile),
                portfolioFit,
                veto,
                synthesis,
                objective.directionPrediction(),
                synthesis.operationalAction(),
                synthesis.operationalActionRatio()
        );
    }

}
