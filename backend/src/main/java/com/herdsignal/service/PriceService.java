package com.herdsignal.service;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.dto.PriceHistoryResponse;
import com.herdsignal.dto.PricePoint;
import com.herdsignal.repository.DailyPriceRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;

/**
 * 종목 일별 종가 히스토리 조회 서비스.
 * daily_prices 테이블에서 period별 날짜 범위 조회 후 DTO 변환.
 * Python 스케줄러가 저장한 데이터를 읽기 전용으로 사용.
 */
@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class PriceService {

    private final DailyPriceRepository dailyPriceRepository;

    /**
     * 종목의 기간별 종가 히스토리 반환 (날짜 오름차순).
     *
     * @param ticker 티커 심볼 (대문자)
     * @param period "1M" | "3M" | "1Y" | "5Y" — 미지원 형식은 1M(30일) 적용
     */
    public PriceHistoryResponse getPriceHistory(String ticker, String period) {
        LocalDate cutoff = parsePeriod(period);
        log.debug("[{}] 가격 히스토리 조회 — period={}, cutoff={}", ticker, period, cutoff);

        List<DailyPrice> prices = dailyPriceRepository.findHistoryByTickerSince(ticker, cutoff);
        List<PricePoint> points = prices.stream()
                .filter(p -> p.getClosePrice() != null)
                .map(p -> PricePoint.builder()
                        .date(p.getPriceDate().toString())
                        .close(p.getClosePrice().doubleValue())
                        .build())
                .toList();

        return PriceHistoryResponse.builder().points(points).build();
    }

    /** "1M"→30일, "3M"→90일, "1Y"→365일, "5Y"→1825일, 그 외 기본 30일 */
    private LocalDate parsePeriod(String period) {
        return switch (period == null ? "" : period.toUpperCase()) {
            case "3M" -> LocalDate.now().minusDays(90);
            case "1Y" -> LocalDate.now().minusDays(365);
            case "5Y" -> LocalDate.now().minusDays(1825);
            default   -> LocalDate.now().minusDays(30);
        };
    }
}
