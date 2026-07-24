package com.herdsignal.service;

import com.herdsignal.domain.HerdIndicator;
import com.herdsignal.domain.HerdScore;
import com.herdsignal.domain.InvestorProfile;
import com.herdsignal.domain.Stock;
import com.herdsignal.dto.ActionDecision;
import com.herdsignal.dto.HerdScoreResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 미리 조회된 HERD 데이터와 개인 행동 컨텍스트를 API 응답으로 조립한다.
 */
@Component
@RequiredArgsConstructor
public class HerdResponseAssembler {

    private final HerdQualityEvaluator qualityEvaluator;
    private final HerdSignalDurationCalculator durationCalculator;
    private final ActionDecisionService actionDecisionService;

    public HerdScoreResponse assemble(
            HerdScore score,
            HerdIndicator indicator,
            List<HerdScore> history,
            Stock stock,
            InvestorProfile profile,
            boolean currentlyHeld,
            ActionCooldownContext cooldown,
            PortfolioActionContext portfolioContext
    ) {
        HerdQualityEvaluator.HerdQuality quality = qualityEvaluator.evaluate(score, indicator);
        ActionDecision actionDecision = actionDecisionService.decide(
                score,
                indicator,
                quality.score(),
                history,
                profile,
                currentlyHeld,
                cooldown,
                portfolioContext
        );
        return HerdScoreResponse.of(
                score,
                indicator,
                quality.score(),
                quality.level(),
                quality.label(),
                quality.summary(),
                quality.flags(),
                quality.reasons(),
                actionDecision,
                stock,
                durationCalculator.calculate(score, history)
        );
    }
}
