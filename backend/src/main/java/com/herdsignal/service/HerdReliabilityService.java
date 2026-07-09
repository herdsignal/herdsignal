package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.dto.HerdReliabilityResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * HERD 신호 신뢰도 조회 서비스.
 * Python signal_reliability.py를 실행해 과거 신호 성능을 계산한다.
 */
@Slf4j
@Service
public class HerdReliabilityService {

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

        Path projectRoot = Paths.get(System.getProperty("user.dir")).getParent();
        Path pythonExe   = projectRoot.resolve("data/.venv/bin/python3.12");

        ProcessBuilder pb = new ProcessBuilder(
                pythonExe.toString(),
                "data/herd/signal_reliability.py",
                ticker,
                "--years",
                String.valueOf(years)
        );
        pb.directory(projectRoot.toFile());

        try {
            Process process = pb.start();

            StringBuilder output = new StringBuilder();
            StringBuilder stderr = new StringBuilder();

            Thread stdoutReader = new Thread(() -> readStream(process, output, ticker, "stdout"));
            Thread stderrReader = new Thread(() -> readStream(process, stderr, ticker, "stderr"));

            stdoutReader.start();
            stderrReader.start();

            boolean finished = process.waitFor(60, TimeUnit.SECONDS);
            stdoutReader.join(5_000);
            stderrReader.join(5_000);

            if (!finished) {
                process.destroyForcibly();
                throw new RuntimeException("[" + ticker + "] HERD 신뢰도 조회 타임아웃 (60초)");
            }

            int exitCode = process.exitValue();
            String stderrStr = stderr.toString().trim();
            if (exitCode != 0) {
                log.error("[herd-reliability][{}] Python 실패 (exit={}):\n{}", ticker, exitCode, stderrStr);
                throw new RuntimeException("[" + ticker + "] HERD 신뢰도 조회 실패 (exit=" + exitCode + ")");
            }
            if (!stderrStr.isEmpty()) {
                log.debug("[herd-reliability][{}] Python 로그:\n{}", ticker, stderrStr);
            }

            String outputStr = output.toString().trim();
            if (outputStr.isEmpty()) {
                throw new RuntimeException("[" + ticker + "] Python 출력 없음");
            }

            ObjectMapper mapper = new ObjectMapper();
            @SuppressWarnings("unchecked")
            Map<String, Object> raw = mapper.readValue(outputStr, Map.class);

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

        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            log.error("[herd-reliability][{}] 조회 실패: {}", ticker, e.getMessage(), e);
            throw new RuntimeException("[" + ticker + "] HERD 신뢰도 조회 실패: " + e.getMessage());
        }
    }

    private void readStream(Process process, StringBuilder target, String ticker, String streamName) {
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader("stdout".equals(streamName)
                        ? process.getInputStream()
                        : process.getErrorStream()))) {
            String line;
            while ((line = reader.readLine()) != null) {
                target.append(line).append("\n");
            }
        } catch (IOException e) {
            log.warn("[herd-reliability][{}] {} 읽기 오류: {}", ticker, streamName, e.getMessage());
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
