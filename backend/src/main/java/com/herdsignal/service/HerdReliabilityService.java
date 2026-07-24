package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import com.herdsignal.dto.HerdReliabilityResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.List;
import java.util.Map;

/**
 * HERD 신호 신뢰도 조회 서비스.
 * Python signal_reliability.py를 실행해 과거 신호 성능을 계산한다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class HerdReliabilityService {
    private final ObjectMapper objectMapper;
    private final PythonProcessGateway processGateway;

    /**
     * 특정 종목의 HERD 신호 신뢰도를 조회한다.
     *
     * @param ticker 티커 심볼
     * @param years 분석 기간(년)
     * @return 신뢰도 응답 DTO
     */
    public HerdReliabilityResponse getReliability(String ticker, int years) {
        if (!ticker.matches("[A-Z0-9\\-\\.]+")) {
            throw new IllegalArgumentException("유효하지 않은 티커 형식: " + ticker);
        }
        if (years < 1 || years > 10) {
            throw new IllegalArgumentException("분석 기간은 1~10년만 허용합니다.");
        }

        try {
            String output = processGateway.executeScript(
                    "[herd-reliability][" + ticker + "]",
                    "data/herd/signal_reliability.py",
                    List.of(ticker, "--years", String.valueOf(years)),
                    Duration.ofSeconds(60)
            ).stdout();
            Map<String, Object> raw = objectMapper.readValue(output, new TypeReference<>() {});

            return HerdReliabilityResponse.builder()
                    .ticker(toStringValue(raw.get("ticker")))
                    .modelVersion(toStringValue(raw.get("model_version")))
                    .periodYears(toInteger(raw.get("period_years")))
                    .historyCount(toInteger(raw.get("history_count")))
                    .fitScore(toInteger(raw.get("fit_score")))
                    .sampleQuality(toStringValue(raw.get("sample_quality")))
                    .totalSignalSamples(toInteger(raw.get("total_signal_samples")))
                    .buySignalEdge(toStringValue(raw.get("buy_signal_edge")))
                    .sellSignalEdge(toStringValue(raw.get("sell_signal_edge")))
                    .reliabilityVerdict(toStringValue(raw.get("reliability_verdict")))
                    .fleeSampleSize(toInteger(raw.get("flee_sample_size")))
                    .fleeHitRate(toDouble(raw.get("flee_hit_rate")))
                    .rushSampleSize(toInteger(raw.get("rush_sample_size")))
                    .rushHitRate(toDouble(raw.get("rush_hit_rate")))
                    .buyReturn1m(toDouble(raw.get("buy_return_1m")))
                    .buyReturn3m(toDouble(raw.get("buy_return_3m")))
                    .buyReturn6m(toDouble(raw.get("buy_return_6m")))
                    .sellDrawdown1m(toDouble(raw.get("sell_drawdown_1m")))
                    .sellDrawdown3m(toDouble(raw.get("sell_drawdown_3m")))
                    .mddImprovement(toDouble(raw.get("mdd_improvement")))
                    .returnPreservation(toDouble(raw.get("return_preservation")))
                    .annualActions(toDouble(raw.get("annual_actions")))
                    .strategyReturn(toDouble(raw.get("strategy_return")))
                    .buyHoldReturn(toDouble(raw.get("buy_hold_return")))
                    .strategyMdd(toDouble(raw.get("strategy_mdd")))
                    .buyHoldMdd(toDouble(raw.get("buy_hold_mdd")))
                    .reliabilityGrade(toStringValue(raw.get("reliability_grade")))
                    .reliabilityLabel(toStringValue(raw.get("reliability_label")))
                    .summary(toStringValue(raw.get("summary")))
                    .lastUpdated(toStringValue(raw.get("last_updated")))
                    .build();

        } catch (Exception e) {
            log.error("[herd-reliability][{}] 조회 실패: {}", ticker, e.getMessage(), e);
            throw new RuntimeException("[" + ticker + "] HERD 신뢰도 조회 실패: " + e.getMessage());
        }
    }

    private Double toDouble(Object val) {
        if (val == null) return null;
        return ((Number) val).doubleValue();
    }

    private Integer toInteger(Object val) {
        if (val == null) return null;
        return ((Number) val).intValue();
    }

    private String toStringValue(Object val) {
        return val == null ? null : val.toString();
    }
}
