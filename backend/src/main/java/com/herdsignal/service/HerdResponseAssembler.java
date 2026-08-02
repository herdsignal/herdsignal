package com.herdsignal.service;

import com.herdsignal.domain.HerdIndicator;
import com.herdsignal.domain.HerdScore;
import com.herdsignal.domain.Stock;
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
    private final HerdScoreResponseMapper responseMapper;

    public HerdScoreResponse assemble(
            HerdScore score,
            HerdIndicator indicator,
            List<HerdScore> history,
            Stock stock
    ) {
        HerdQualityEvaluator.HerdQuality quality = qualityEvaluator.evaluate(score, indicator);
        return responseMapper.map(
                score,
                indicator,
                quality,
                stock,
                durationCalculator.calculate(score, history)
        );
    }
}
