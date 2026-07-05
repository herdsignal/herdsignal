package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.dto.StockSearchItem;
import com.herdsignal.dto.StockSearchResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * Finnhub 심볼 검색 서비스.
 * ProcessBuilder로 Python finnhub_collector.search_symbols를 실행한다.
 * FinancialsService와 동일한 ProcessBuilder 패턴 사용.
 */
@Slf4j
@Service
public class FinnhubService {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    /**
     * 회사명 또는 티커 기반 종목 검색.
     * Finnhub 실패 시 빈 결과를 반환한다.
     */
    public StockSearchResponse searchStocks(String query) {
        String normalized = validateSearchQuery(query);
        try {
            String queryLiteral = MAPPER.writeValueAsString(normalized);
            String script = String.join("\n",
                "import sys, json",
                "sys.path.insert(0, 'data')",
                "from collectors.finnhub_collector import search_symbols",
                "query = " + queryLiteral,
                "print(json.dumps(search_symbols(query)))"
            );
            String json = runPython(normalized, "search", script);
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> raw = MAPPER.readValue(json, List.class);
            List<StockSearchItem> items = raw.stream()
                    .map(m -> StockSearchItem.builder()
                            .ticker((String) m.get("ticker"))
                            .name((String) m.get("name"))
                            .type((String) m.get("type"))
                            .displaySymbol((String) m.get("display_symbol"))
                            .build())
                    .toList();
            return StockSearchResponse.builder()
                    .query(normalized)
                    .results(items)
                    .build();
        } catch (Exception e) {
            log.warn("[finnhub/search][{}] 조회 실패: {}", normalized, e.getMessage());
            return StockSearchResponse.builder()
                    .query(normalized)
                    .results(List.of())
                    .build();
        }
    }

    /** 검색어 유효성 검사 — 외부 API 남용과 불필요한 긴 입력 방지 */
    private String validateSearchQuery(String query) {
        String normalized = query == null ? "" : query.trim();
        if (normalized.length() < 1 || normalized.length() > 50) {
            throw new IllegalArgumentException("검색어는 1~50자여야 합니다.");
        }
        if (!normalized.matches("[A-Za-z0-9 .,'&\\-]+")) {
            throw new IllegalArgumentException("지원하지 않는 검색어 형식입니다.");
        }
        return normalized;
    }

    /**
     * Python 스크립트를 ProcessBuilder로 실행하고 stdout 반환.
     * FinancialsService와 동일한 패턴 (stdout/stderr 분리 스레드, 타임아웃 30초).
     *
     * @param ticker  로그용 티커 심볼
     * @param context 로그용 컨텍스트
     * @param script  실행할 Python 코드 문자열
     * @return Python stdout (trim 처리)
     * @throws Exception 타임아웃, 비정상 종료, 출력 없음 시
     */
    private String runPython(String ticker, String context, String script) throws Exception {
        Path projectRoot = Paths.get(System.getProperty("user.dir")).getParent();
        Path pythonExe   = projectRoot.resolve("data/.venv/bin/python3.12");

        ProcessBuilder pb = new ProcessBuilder(pythonExe.toString(), "-c", script);
        pb.directory(projectRoot.toFile());

        Process process = pb.start();

        StringBuilder output = new StringBuilder();
        Thread stdoutReader = new Thread(() -> {
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) output.append(line).append("\n");
            } catch (IOException ignored) {}
        });
        Thread stderrReader = new Thread(() -> {
            try { process.getErrorStream().readAllBytes(); } catch (IOException ignored) {}
        });
        stdoutReader.start();
        stderrReader.start();

        boolean finished = process.waitFor(30, TimeUnit.SECONDS);
        stdoutReader.join(5_000);
        stderrReader.join(1_000);

        if (!finished) {
            process.destroyForcibly();
            throw new RuntimeException("[" + ticker + "][" + context + "] 타임아웃 (30초)");
        }
        if (process.exitValue() != 0) {
            throw new RuntimeException("[" + ticker + "][" + context + "] exit=" + process.exitValue());
        }

        String result = output.toString().trim();
        if (result.isEmpty()) {
            throw new RuntimeException("[" + ticker + "][" + context + "] Python 출력 없음");
        }
        return result;
    }
}
