package com.herdsignal.service.decision;

import com.herdsignal.domain.InvestorProfile;
import com.herdsignal.service.CurrentUserService;
import com.herdsignal.service.InvestorProfileService;
import com.herdsignal.service.PortfolioActionContext;
import com.herdsignal.service.PortfolioActionContextService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** 객관적 관찰과 개인 맥락을 결합하되 행동 권한은 별도로 잠근다. */
@Service
@RequiredArgsConstructor
public class LongTermOperatingReviewService {
    private final ObjectiveEvidenceService objectiveEvidenceService;
    private final CurrentUserService currentUserService;
    private final InvestorProfileService investorProfileService;
    private final PortfolioActionContextService portfolioActionContextService;
    private final DecisionSynthesisPolicy synthesisPolicy;

    public PersonalOperatingReviewResponse review(String ticker) {
        ObjectiveReviewResponse objective = objectiveEvidenceService.review(ticker);
        String userId = currentUserService.requireUserId();
        InvestorProfile profile = investorProfileService.forDecision(userId);
        PortfolioActionContext context = portfolioActionContextService.getContexts(
                        userId, List.of(objective.ticker()), profile)
                .getOrDefault(objective.ticker(), PortfolioActionContext.unavailable());
        RiskVeto veto = riskVeto(objective);
        PortfolioFitAssessment portfolioFit = portfolioFit(context);
        DecisionSynthesis synthesis = synthesisPolicy.synthesize(objective, portfolioFit, veto);

        return new PersonalOperatingReviewResponse(
                synthesis.decision().name(),
                objective.ticker(),
                objective,
                OperatingMandate.from(profile),
                portfolioFit,
                veto,
                synthesis,
                synthesis.actionAuthorized(),
                synthesis.operationalAction(),
                synthesis.operationalActionRatio()
        );
    }

    private PortfolioFitAssessment portfolioFit(PortfolioActionContext context) {
        if (!context.available()) {
            return new PortfolioFitAssessment(
                    AssessmentStatus.NO_VIEW, false, false, 0.0, 0.0, 0.0,
                    "포트폴리오 비중 없음",
                    "보유 수량·시세·현금이 모두 확인돼야 개인 비중을 계산합니다.");
        }
        boolean held = context.currentTickerWeight() > 0.0;
        return new PortfolioFitAssessment(
                AssessmentStatus.AVAILABLE,
                true,
                held,
                context.currentTickerWeight(),
                context.currentEquityRatio(),
                context.targetEquityRatio(),
                held ? "현재 보유 비중 확인" : "현재 미보유",
                "개별 종목 목표 비중이 없으므로 과대·과소 비중을 추정하지 않습니다."
        );
    }

    private RiskVeto riskVeto(ObjectiveReviewResponse objective) {
        List<String> codes = new ArrayList<>();
        if (!objective.dataGate().open()) {
            codes.add("DATA_GATE_BLOCKED");
        }
        if (hasNoView(objective, DecisionArea.BUSINESS_HEALTH)) {
            codes.add("BUSINESS_HEALTH_NOT_CONNECTED");
        }
        if (hasNoView(objective, DecisionArea.INFORMATION_CHANGE)) {
            codes.add("DIRECTIONAL_EVIDENCE_NOT_ADOPTED");
        }
        return new RiskVeto(
                true,
                codes,
                "운영 행동 권한 없음"
        );
    }

    private boolean hasNoView(ObjectiveReviewResponse objective, DecisionArea area) {
        return objective.assessments().stream()
                .anyMatch(item -> item.area() == area && item.status() == AssessmentStatus.NO_VIEW);
    }
}
