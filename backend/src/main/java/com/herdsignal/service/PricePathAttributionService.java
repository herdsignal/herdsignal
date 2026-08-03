package com.herdsignal.service;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.repository.DailyPriceRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.List;

/** 저장 시점 종가에서 고정 달력 기간 뒤의 실제 가격 경로만 계산한다. */
@Service
@RequiredArgsConstructor
public class PricePathAttributionService {
    private static final int PRICE_LOOKUP_DAYS = 7;

    private final DailyPriceRepository dailyPriceRepository;

    public List<Outcome> evaluate(
            String ticker,
            LocalDate referenceDate,
            BigDecimal referencePrice,
            List<Integer> horizonMonths,
            LocalDate latestMarketDate
    ) {
        if (referenceDate == null || referencePrice == null
                || referencePrice.compareTo(BigDecimal.ZERO) <= 0) {
            return horizonMonths.stream()
                    .map(months -> unavailable(months,
                            referenceDate == null ? null : referenceDate.plusMonths(months)))
                    .toList();
        }
        return horizonMonths.stream()
                .map(months -> evaluateHorizon(
                        ticker, referenceDate, referencePrice, months, latestMarketDate))
                .toList();
    }

    private Outcome evaluateHorizon(
            String ticker,
            LocalDate referenceDate,
            BigDecimal referencePrice,
            int months,
            LocalDate latestMarketDate
    ) {
        LocalDate targetDate = referenceDate.plusMonths(months);
        if (latestMarketDate == null || targetDate.isAfter(latestMarketDate)) {
            return new Outcome(months, targetDate, "PENDING", null, null, null);
        }
        DailyPrice target = dailyPriceRepository
                .findTopByTickerAndPriceDateBetweenAndClosePriceIsNotNullOrderByPriceDateAsc(
                        ticker, targetDate, targetDate.plusDays(PRICE_LOOKUP_DAYS))
                .orElse(null);
        if (target == null) return unavailable(months, targetDate);
        BigDecimal returnPct = target.getClosePrice()
                .divide(referencePrice, 10, RoundingMode.HALF_UP)
                .subtract(BigDecimal.ONE)
                .multiply(BigDecimal.valueOf(100))
                .setScale(4, RoundingMode.HALF_UP);
        return new Outcome(
                months, targetDate, "AVAILABLE", target.getPriceDate(),
                target.getClosePrice(), returnPct);
    }

    private Outcome unavailable(int months, LocalDate targetDate) {
        return new Outcome(months, targetDate, "UNAVAILABLE", null, null, null);
    }

    public record Outcome(
            int horizonMonths,
            LocalDate targetDate,
            String status,
            LocalDate priceDate,
            BigDecimal closePrice,
            BigDecimal returnPct
    ) {
    }
}
