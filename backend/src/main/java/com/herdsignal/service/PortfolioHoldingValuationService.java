package com.herdsignal.service;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.dto.StockHoldingResponse;
import com.herdsignal.repository.DailyPriceRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.Optional;

/**
 * 한 보유 종목의 현재 평가값을 계산한다.
 *
 * <p>가격 조회와 금액 계산을 포트폴리오 조회 오케스트레이션에서 분리한다.</p>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PortfolioHoldingValuationService {

    private final DailyPriceRepository dailyPriceRepository;

    public StockHoldingResponse value(UserPortfolio holding, LocalDate marketSessionDate) {
        Optional<DailyPrice> currentPriceOpt =
                dailyPriceRepository.findTopByTickerAndPriceDateLessThanEqualAndClosePriceIsNotNullOrderByPriceDateDesc(
                        holding.getTicker(),
                        marketSessionDate
                );

        if (currentPriceOpt.isEmpty()) {
            log.warn("[{}] daily_prices 종가 없음 — 종목 제외", holding.getTicker());
            return null;
        }

        DailyPrice currentDailyPrice = currentPriceOpt.get();
        BigDecimal currentPrice = currentDailyPrice.getClosePrice();
        BigDecimal avgPrice = holding.getAvgPrice();
        BigDecimal quantity = holding.getQuantity();

        BigDecimal marketValue = currentPrice.multiply(quantity);
        BigDecimal returnPct = currentPrice.subtract(avgPrice)
                .divide(avgPrice, 4, RoundingMode.HALF_UP)
                .multiply(BigDecimal.valueOf(100));

        BigDecimal dailyChangePct = calculateDailyChange(
                holding.getTicker(), currentDailyPrice, marketSessionDate);

        return StockHoldingResponse.builder()
                .ticker(holding.getTicker())
                .avgPrice(avgPrice.setScale(2, RoundingMode.HALF_UP))
                .quantity(quantity.setScale(4, RoundingMode.HALF_UP))
                .currentPrice(currentPrice.setScale(2, RoundingMode.HALF_UP))
                .priceDate(currentDailyPrice.getPriceDate())
                .marketValue(marketValue.setScale(2, RoundingMode.HALF_UP))
                .returnPct(returnPct.setScale(2, RoundingMode.HALF_UP))
                .dailyChangePct(dailyChangePct.setScale(2, RoundingMode.HALF_UP))
                .build();
    }

    private BigDecimal calculateDailyChange(
            String ticker,
            DailyPrice currentDailyPrice,
            LocalDate marketSessionDate
    ) {
        if (currentDailyPrice.getPriceDate().isBefore(marketSessionDate)) {
            return BigDecimal.ZERO;
        }

        return dailyPriceRepository
                .findTopByTickerAndPriceDateLessThanAndClosePriceIsNotNullOrderByPriceDateDesc(
                        ticker,
                        currentDailyPrice.getPriceDate()
                )
                .map(DailyPrice::getClosePrice)
                .filter(previous -> previous.compareTo(BigDecimal.ZERO) != 0)
                .map(previous -> currentDailyPrice.getClosePrice()
                        .subtract(previous)
                        .divide(previous, 4, RoundingMode.HALF_UP)
                        .multiply(BigDecimal.valueOf(100)))
                .orElse(BigDecimal.ZERO);
    }
}
