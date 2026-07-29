package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import com.herdsignal.dto.StockFinancialsResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.Map;

/**
 * 개별 종목 재무정보 조회 서비스.
 * 공통 Python 실행 게이트웨이로 stock_info_collector를 실행해 재무 지표를 반환한다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class FinancialsService {
    private final ObjectMapper objectMapper;
    private final PythonProcessGateway processGateway;
    private final TickerSymbolPolicy tickerSymbolPolicy;

    /**
     * 종목 재무정보를 조회한다.
     * Python stock_info_collector.get_stock_financials(ticker)를 실행하고
     * stdout JSON을 파싱해 반환한다. 타임아웃 30초.
     *
     * @param ticker 유효성이 검증된 티커 심볼 (대문자, 영숫자·하이픈·점만 허용)
     * @return 재무정보 DTO
     * @throws RuntimeException Python 실행 실패 또는 타임아웃 시
     */
    public StockFinancialsResponse getFinancials(String ticker) {
        String normalizedTicker = tickerSymbolPolicy.normalize(ticker);

        try {
            String tickerLiteral = objectMapper.writeValueAsString(normalizedTicker);
            String script = String.join("\n",
                    "import sys, json",
                    "sys.path.insert(0, 'data')",
                    "from collectors.stock_info_collector import get_stock_financials",
                    "print(json.dumps(get_stock_financials(" + tickerLiteral + ")))"
            );
            String output = processGateway.executeInline(
                    "[financials][" + normalizedTicker + "]", script, Duration.ofSeconds(30)).stdout();
            Map<String, Object> raw = objectMapper.readValue(output, new TypeReference<>() {});

            return StockFinancialsResponse.builder()
                    .ticker((String) raw.get("ticker"))
                    .marketCap(toDouble(raw.get("market_cap")))
                    .trailingPe(toDouble(raw.get("trailing_pe")))
                    .eps(toDouble(raw.get("eps")))
                    .operatingMargin(toDouble(raw.get("operating_margin")))
                    .totalRevenue(toDouble(raw.get("total_revenue")))
                    .dividendYield(toDouble(raw.get("dividend_yield")))
                    .build();

        } catch (Exception e) {
            log.error("[financials][{}] 재무정보 조회 실패: {}", normalizedTicker, e.getMessage(), e);
            throw new RuntimeException(
                    "[" + normalizedTicker + "] 재무정보 조회 실패: " + e.getMessage(), e);
        }
    }

    /** JSON Number → Double 변환. null이면 null 반환. */
    private Double toDouble(Object val) {
        if (val == null) return null;
        return ((Number) val).doubleValue();
    }
}
