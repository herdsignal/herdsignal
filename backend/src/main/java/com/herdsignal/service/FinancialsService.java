package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.dto.StockFinancialsResponse;
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
 * 개별 종목 재무정보 조회 서비스.
 * ProcessBuilder로 Python stock_info_collector를 실행해 재무 지표를 반환한다.
 * MarketService와 동일한 ProcessBuilder 패턴 사용.
 */
@Slf4j
@Service
public class FinancialsService {

    /**
     * 종목 재무정보를 조회한다.
     * Python stock_info_collector.get_stock_financials(ticker)를 ProcessBuilder로 실행하고
     * stdout JSON을 파싱해 반환한다. 타임아웃 30초.
     *
     * @param ticker 유효성이 검증된 티커 심볼 (대문자, 영숫자·하이픈·점만 허용)
     * @return 재무정보 DTO
     * @throws RuntimeException Python 실행 실패 또는 타임아웃 시
     */
    public StockFinancialsResponse getFinancials(String ticker) {
        // 티커 유효성 검사 — 코드 주입 방지 (HerdService와 동일 규칙)
        if (!ticker.matches("[A-Z0-9\\-\\.]+")) {
            throw new IllegalArgumentException("유효하지 않은 티커 형식: " + ticker);
        }

        Path projectRoot = Paths.get(System.getProperty("user.dir")).getParent();
        Path pythonExe   = projectRoot.resolve("data/.venv/bin/python3.12");

        String script = String.join("\n",
            "import sys, json",
            "sys.path.insert(0, 'data')",
            "from collectors.stock_info_collector import get_stock_financials",
            "print(json.dumps(get_stock_financials('" + ticker + "')))"
        );

        ProcessBuilder pb = new ProcessBuilder(pythonExe.toString(), "-c", script);
        pb.directory(projectRoot.toFile());

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
                    log.warn("[financials][{}] stdout 읽기 오류: {}", ticker, e.getMessage());
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
                    log.warn("[financials][{}] stderr 읽기 오류: {}", ticker, e.getMessage());
                }
            });

            stdoutReader.start();
            stderrReader.start();

            boolean finished = process.waitFor(30, TimeUnit.SECONDS);
            stdoutReader.join(5_000);
            stderrReader.join(5_000);

            if (!finished) {
                process.destroyForcibly();
                throw new RuntimeException("[" + ticker + "] 재무정보 조회 타임아웃 (30초)");
            }

            int exitCode = process.exitValue();
            String stderrStr = stderr.toString().trim();

            if (exitCode != 0) {
                log.error("[financials][{}] Python 실패 (exit={}):\n{}", ticker, exitCode, stderrStr);
                throw new RuntimeException("[" + ticker + "] 재무정보 조회 실패 (exit=" + exitCode + ")");
            }
            if (!stderrStr.isEmpty()) {
                log.debug("[financials][{}] Python 로그:\n{}", ticker, stderrStr);
            }

            String outputStr = output.toString().trim();
            if (outputStr.isEmpty()) {
                throw new RuntimeException("[" + ticker + "] Python 출력 없음");
            }

            // JSON 파싱 — Python snake_case 키를 직접 읽어 DTO로 변환
            ObjectMapper mapper = new ObjectMapper();
            @SuppressWarnings("unchecked")
            Map<String, Object> raw = mapper.readValue(outputStr, Map.class);

            return StockFinancialsResponse.builder()
                    .ticker((String) raw.get("ticker"))
                    .marketCap(toDouble(raw.get("market_cap")))
                    .trailingPe(toDouble(raw.get("trailing_pe")))
                    .eps(toDouble(raw.get("eps")))
                    .operatingMargin(toDouble(raw.get("operating_margin")))
                    .totalRevenue(toDouble(raw.get("total_revenue")))
                    .dividendYield(toDouble(raw.get("dividend_yield")))
                    .build();

        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            log.error("[financials][{}] 재무정보 조회 실패: {}", ticker, e.getMessage(), e);
            throw new RuntimeException("[" + ticker + "] 재무정보 조회 실패: " + e.getMessage());
        }
    }

    /** JSON Number → Double 변환. null이면 null 반환. */
    private Double toDouble(Object val) {
        if (val == null) return null;
        return ((Number) val).doubleValue();
    }
}
