package com.herdsignal.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.time.Duration;
import java.util.List;

/** Python 데이터 엔진의 on-demand HERD 계산을 격리해 실행한다. */
@Slf4j
@Component
public class HerdOnDemandRunner {
    private static final int SINGLE_TIMEOUT_SECONDS = 30;
    private static final int BATCH_TIMEOUT_SECONDS = 120;

    private final ObjectMapper objectMapper;
    private final PythonProcessGateway processGateway;
    private final TickerSymbolPolicy tickerSymbolPolicy;

    public HerdOnDemandRunner(
            ObjectMapper objectMapper,
            PythonProcessGateway processGateway,
            TickerSymbolPolicy tickerSymbolPolicy
    ) {
        this.objectMapper = objectMapper;
        this.processGateway = processGateway;
        this.tickerSymbolPolicy = tickerSymbolPolicy;
    }

    public void refresh(String ticker, boolean force) throws IOException, InterruptedException {
        String normalizedTicker = normalizeTickers(List.of(ticker)).get(0);
        String pythonTicker = objectMapper.writeValueAsString(normalizedTicker);
        String code = String.join("\n",
                "import json, sys",
                "sys.path.insert(0, 'data')",
                "from scheduler.herd_scheduler import calculate_on_demand",
                "result = calculate_on_demand(" + pythonTicker + ", force=" + pythonBoolean(force) + ")",
                "print(json.dumps(result))"
        );
        String output = processGateway.executeInline(
                "[" + normalizedTicker + "]",
                code,
                Duration.ofSeconds(SINGLE_TIMEOUT_SECONDS)
        ).stdout();
        log.info("[{}] Python on-demand 완료: {}", normalizedTicker, output);
    }

    public void refreshMany(List<String> tickers, boolean force) throws IOException, InterruptedException {
        List<String> normalizedTickers = normalizeTickers(tickers);
        if (normalizedTickers.isEmpty()) {
            return;
        }
        String pythonTickers = objectMapper.writeValueAsString(normalizedTickers);
        String code = String.join("\n",
                "import json, sys",
                "sys.path.insert(0, 'data')",
                "from scheduler.herd_scheduler import calculate_many_on_demand",
                "result = calculate_many_on_demand(" + pythonTickers + ", force=" + pythonBoolean(force) + ")",
                "print(json.dumps(result))"
        );
        String output = processGateway.executeInline(
                "[portfolio]",
                code,
                Duration.ofSeconds(BATCH_TIMEOUT_SECONDS)
        ).stdout();
        failOnBatchErrors(output);
        log.info("[portfolio] Python on-demand 배치 완료: {}", output);
    }

    List<String> normalizeTickers(List<String> tickers) {
        if (tickers == null) {
            throw new IllegalArgumentException("티커 목록이 필요합니다.");
        }
        return tickers.stream()
                .map(tickerSymbolPolicy::normalize)
                .distinct()
                .toList();
    }

    void failOnBatchErrors(String output) throws IOException {
        String jsonLine = null;
        for (String line : output.split("\\R")) {
            String trimmed = line.trim();
            if (trimmed.startsWith("{") && trimmed.contains("\"errors\"")) {
                jsonLine = trimmed;
            }
        }
        if (jsonLine == null) {
            return;
        }
        JsonNode errors = objectMapper.readTree(jsonLine).path("errors");
        if (errors.isArray() && !errors.isEmpty()) {
            throw new IOException("[portfolio] 일부 HERD 갱신 실패: " + errors);
        }
    }

    private String pythonBoolean(boolean value) {
        return value ? "True" : "False";
    }
}
