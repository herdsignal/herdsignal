package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.dto.SpyMarketResponse;
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
 * 시장 레퍼런스 데이터 조회 서비스.
 * ProcessBuilder로 Python market_collector를 실행해 SPY 현재가·1개월 수익률을 반환한다.
 * PortfolioService.getRealtimePortfolio()와 동일한 ProcessBuilder 패턴 사용.
 */
@Slf4j
@Service
public class MarketService {

    /**
     * SPY 현재가와 1개월 수익률을 조회한다.
     * Python market_collector.get_spy_market_data()를 ProcessBuilder로 실행하고
     * stdout JSON을 파싱해 반환한다. 타임아웃 30초.
     *
     * @return SPY 시장 데이터
     * @throws RuntimeException Python 실행 실패 또는 타임아웃 시
     */
    public SpyMarketResponse getSpyMarketData() {
        Path projectRoot = Paths.get(System.getProperty("user.dir")).getParent();
        Path pythonExe   = projectRoot.resolve("data/.venv/bin/python3.12");

        String script = String.join("\n",
            "import sys, json",
            "sys.path.insert(0, 'data')",
            "from collectors.market_collector import get_spy_market_data",
            "print(json.dumps(get_spy_market_data()))"
        );

        ProcessBuilder pb = new ProcessBuilder(pythonExe.toString(), "-c", script);
        pb.directory(projectRoot.toFile());
        pb.environment().remove("DB_PASSWORD");

        try {
            Process process = pb.start();

            StringBuilder output = new StringBuilder();
            StringBuilder stderr  = new StringBuilder();

            // stdout·stderr 별도 스레드 읽기 — 파이프 버퍼 데드락 방지
            Thread stdoutReader = new Thread(() -> {
                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(process.getInputStream()))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        output.append(line).append("\n");
                    }
                } catch (IOException e) {
                    log.warn("[market] stdout 읽기 오류: {}", e.getMessage());
                }
            });

            Thread stderrReader = new Thread(() -> {
                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(process.getErrorStream()))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        stderr.append(line).append("\n");
                    }
                } catch (IOException e) {
                    log.warn("[market] stderr 읽기 오류: {}", e.getMessage());
                }
            });

            stdoutReader.start();
            stderrReader.start();

            boolean finished = process.waitFor(30, TimeUnit.SECONDS);
            stdoutReader.join(5_000);
            stderrReader.join(5_000);

            if (!finished) {
                process.destroyForcibly();
                throw new RuntimeException("SPY 시장 데이터 조회 타임아웃 (30초)");
            }

            int exitCode = process.exitValue();
            String stderrStr = stderr.toString().trim();

            if (exitCode != 0) {
                log.error("[market] Python 실패 (exit={}):\n{}", exitCode, stderrStr);
                throw new RuntimeException("SPY 시장 데이터 조회 실패 (exit=" + exitCode + ")");
            }
            if (!stderrStr.isEmpty()) {
                log.debug("[market] Python 로그:\n{}", stderrStr);
            }

            String outputStr = output.toString().trim();
            if (outputStr.isEmpty()) {
                throw new RuntimeException("Python 출력 없음");
            }

            // JSON 파싱 — Python snake_case 키를 직접 읽어 DTO로 변환
            ObjectMapper mapper = new ObjectMapper();
            @SuppressWarnings("unchecked")
            Map<String, Object> raw = mapper.readValue(outputStr, Map.class);

            return SpyMarketResponse.builder()
                    .ticker((String) raw.get("ticker"))
                    .currentPrice(((Number) raw.get("current_price")).doubleValue())
                    .return1mPct(((Number) raw.get("return_1m_pct")).doubleValue())
                    .priceDate((String) raw.get("price_date"))
                    .build();

        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            log.error("[market] SPY 시장 데이터 조회 실패: {}", e.getMessage(), e);
            throw new RuntimeException("SPY 시장 데이터 조회 실패: " + e.getMessage());
        }
    }
}
