package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.dto.StockSearchItem;
import com.herdsignal.dto.StockSearchResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.List;
import java.util.Map;

/**
 * Finnhub 심볼 검색 서비스.
 * 공통 Python 실행 게이트웨이로 finnhub_collector.search_symbols를 실행한다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class FinnhubService {
    private final ObjectMapper objectMapper;
    private final PythonProcessGateway processGateway;

    /**
     * 회사명 또는 티커 기반 종목 검색.
     * Finnhub 실패 시 빈 결과를 반환한다.
     */
    public StockSearchResponse searchStocks(String query) {
        String normalized = validateSearchQuery(query);
        try {
            String queryLiteral = objectMapper.writeValueAsString(normalized);
            String script = String.join("\n",
                "import sys, json",
                "sys.path.insert(0, 'data')",
                "from collectors.finnhub_collector import search_symbols",
                "query = " + queryLiteral,
                "print(json.dumps(search_symbols(query)))"
            );
            String json = processGateway.executeInline(
                    "[finnhub/search][" + normalized + "]",
                    script,
                    Duration.ofSeconds(30)
            ).stdout();
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> raw = objectMapper.readValue(json, List.class);
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

}
