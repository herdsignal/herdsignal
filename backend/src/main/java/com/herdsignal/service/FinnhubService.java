package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.dto.AnalystResponse;
import com.herdsignal.dto.InsiderResponse;
import com.herdsignal.dto.InsiderTransaction;
import com.herdsignal.dto.NewsItem;
import com.herdsignal.dto.NewsResponse;
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
 * Finnhub API 데이터 조회 서비스.
 * ProcessBuilder로 Python finnhub_collector를 실행해 뉴스·애널리스트·내부자거래를 반환한다.
 * FinancialsService와 동일한 ProcessBuilder 패턴 사용.
 *
 * 공통 동작:
 * - API 실패, 키 미설정, 타임아웃 시 빈 응답 반환 (예외 전파 없음).
 * - 각 메서드가 독립적이므로 한 엔드포인트 실패가 다른 엔드포인트에 영향 없음.
 */
@Slf4j
@Service
public class FinnhubService {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    /**
     * 최근 30일 뉴스 최대 5건 조회.
     * Finnhub 키 미설정 또는 실패 시 빈 리스트 반환.
     */
    public NewsResponse getNews(String ticker) {
        validateTicker(ticker);
        String script = String.join("\n",
            "import sys, json",
            "sys.path.insert(0, 'data')",
            "from collectors.finnhub_collector import get_company_news",
            "print(json.dumps(get_company_news('" + ticker + "')))"
        );
        try {
            String json = runPython(ticker, "news", script);
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> raw = MAPPER.readValue(json, List.class);
            List<NewsItem> items = raw.stream()
                    .map(m -> NewsItem.builder()
                            .headline((String) m.get("headline"))
                            .source((String) m.get("source"))
                            .url((String) m.get("url"))
                            .date((String) m.get("date"))
                            .build())
                    .toList();
            return NewsResponse.builder().news(items).build();
        } catch (Exception e) {
            log.warn("[finnhub/news][{}] 조회 실패: {}", ticker, e.getMessage());
            return NewsResponse.builder().news(List.of()).build();
        }
    }

    /**
     * 최신 1개월 애널리스트 추천 컨센서스 조회.
     * 데이터 없거나 실패 시 null 반환.
     */
    public AnalystResponse getAnalyst(String ticker) {
        validateTicker(ticker);
        String script = String.join("\n",
            "import sys, json",
            "sys.path.insert(0, 'data')",
            "from collectors.finnhub_collector import get_recommendation_trends",
            "result = get_recommendation_trends('" + ticker + "')",
            "print(json.dumps(result if result is not None else {}))"
        );
        try {
            String json = runPython(ticker, "analyst", script);
            @SuppressWarnings("unchecked")
            Map<String, Object> raw = MAPPER.readValue(json, Map.class);
            if (raw.isEmpty()) return null;
            return AnalystResponse.builder()
                    .strongBuy(toInt(raw.get("strong_buy")))
                    .buy(toInt(raw.get("buy")))
                    .hold(toInt(raw.get("hold")))
                    .sell(toInt(raw.get("sell")))
                    .strongSell(toInt(raw.get("strong_sell")))
                    .total(toInt(raw.get("total")))
                    .consensus((String) raw.get("consensus"))
                    .period((String) raw.get("period"))
                    .build();
        } catch (Exception e) {
            log.warn("[finnhub/analyst][{}] 조회 실패: {}", ticker, e.getMessage());
            return null;
        }
    }

    /**
     * 최근 내부자 거래 최대 10건 조회.
     * 실패 시 빈 리스트 반환.
     */
    public InsiderResponse getInsider(String ticker) {
        validateTicker(ticker);
        String script = String.join("\n",
            "import sys, json",
            "sys.path.insert(0, 'data')",
            "from collectors.finnhub_collector import get_insider_transactions",
            "print(json.dumps(get_insider_transactions('" + ticker + "')))"
        );
        try {
            String json = runPython(ticker, "insider", script);
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> raw = MAPPER.readValue(json, List.class);
            List<InsiderTransaction> txs = raw.stream()
                    .map(m -> InsiderTransaction.builder()
                            .name((String) m.get("name"))
                            .transactionCode((String) m.get("transaction_code"))
                            .share(toLong(m.get("share")))
                            .date((String) m.get("date"))
                            .build())
                    .toList();
            return InsiderResponse.builder().transactions(txs).build();
        } catch (Exception e) {
            log.warn("[finnhub/insider][{}] 조회 실패: {}", ticker, e.getMessage());
            return InsiderResponse.builder().transactions(List.of()).build();
        }
    }

    /** 티커 유효성 검사 — 영숫자·하이픈·점만 허용 (코드 주입 방지) */
    private void validateTicker(String ticker) {
        if (!ticker.matches("[A-Z0-9\\-\\.]+")) {
            throw new IllegalArgumentException("유효하지 않은 티커 형식: " + ticker);
        }
    }

    /**
     * Python 스크립트를 ProcessBuilder로 실행하고 stdout 반환.
     * FinancialsService와 동일한 패턴 (stdout/stderr 분리 스레드, 타임아웃 30초).
     *
     * @param ticker  로그용 티커 심볼
     * @param context 로그용 컨텍스트 (news / analyst / insider)
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

    private Integer toInt(Object val) {
        if (val == null) return 0;
        return ((Number) val).intValue();
    }

    private Long toLong(Object val) {
        if (val == null) return 0L;
        return ((Number) val).longValue();
    }
}
