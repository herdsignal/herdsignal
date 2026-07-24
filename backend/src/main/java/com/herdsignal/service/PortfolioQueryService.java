package com.herdsignal.service;

import com.herdsignal.domain.PortfolioHistory;
import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.dto.PortfolioHistoryResponse;
import com.herdsignal.dto.PortfolioSummaryResponse;
import com.herdsignal.dto.StockHoldingResponse;
import com.herdsignal.repository.PortfolioHistoryRepository;
import com.herdsignal.repository.UserPortfolioRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * 포트폴리오 읽기 모델을 조립한다.
 *
 * <p>보유 종목 평가와 현금 원장은 각 전용 서비스에 위임하고, 이 클래스는 API 응답
 * 단위의 집계만 담당한다.</p>
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class PortfolioQueryService {

    private final UserPortfolioRepository portfolioRepository;
    private final PortfolioHistoryRepository historyRepository;
    private final PortfolioHoldingValuationService valuationService;
    private final PortfolioCashService cashService;
    private final UsMarketSessionClock marketSessionClock;

    public PortfolioSummaryResponse getSummary(String userId) {
        LocalDate marketSessionDate = marketSessionClock.currentSessionDate();
        List<UserPortfolio> holdings = portfolioRepository.findByUserId(userId)
                .stream()
                .filter(this::hasPosition)
                .toList();

        List<StockHoldingResponse> stocks = holdings.stream()
                .map(holding -> valuationService.value(holding, marketSessionDate))
                .filter(Objects::nonNull)
                .toList();
        LocalDate marketDataDate = stocks.stream()
                .map(StockHoldingResponse::getPriceDate)
                .filter(Objects::nonNull)
                .min(LocalDate::compareTo)
                .orElse(null);

        BigDecimal cashBalance = cashService.currentAmount(userId);
        PortfolioTotals totals = totalsFromHoldings(holdings, stocks);

        return PortfolioSummaryResponse.builder()
                .totalValue(scale(totals.totalValue()))
                .investedValue(scale(totals.totalValue()))
                .cashBalance(scale(cashBalance))
                .totalAssetValue(scale(totals.totalValue().add(cashBalance)))
                .totalCost(scale(totals.totalCost()))
                .totalReturnPct(scale(totals.totalReturnPct()))
                .dailyChangePct(scale(totals.dailyChangePct()))
                .marketDataDate(marketDataDate)
                .stocks(stocks)
                .build();
    }

    public PortfolioHistoryResponse getHistory(String userId, String period) {
        LocalDate end = LocalDate.now();
        LocalDate start = startDate(period, end);
        List<PortfolioHistory> histories =
                historyRepository.findByUserIdAndSnapshotDateBetweenOrderBySnapshotDateAsc(
                        userId, start, end);
        Map<LocalDate, BigDecimal> cashByDate =
                cashService.historyAtPortfolioDates(userId, start, end, histories);

        List<PortfolioHistoryResponse.HistoryPoint> points = histories.stream()
                .map(history -> toHistoryPoint(history, cashByDate))
                .toList();
        return PortfolioHistoryResponse.builder().points(points).build();
    }

    private PortfolioTotals totalsFromHoldings(
            List<UserPortfolio> holdings,
            List<StockHoldingResponse> stocks
    ) {
        BigDecimal totalValue = stocks.stream()
                .map(StockHoldingResponse::getMarketValue)
                .reduce(BigDecimal.ZERO, BigDecimal::add);
        Map<String, UserPortfolio> holdingByTicker = holdings.stream()
                .collect(java.util.stream.Collectors.toMap(
                        UserPortfolio::getTicker,
                        holding -> holding,
                        (first, ignored) -> first
                ));
        BigDecimal totalCost = stocks.stream()
                .map(StockHoldingResponse::getTicker)
                .map(holdingByTicker::get)
                .filter(Objects::nonNull)
                .map(holding -> holding.getAvgPrice().multiply(holding.getQuantity()))
                .reduce(BigDecimal.ZERO, BigDecimal::add);
        BigDecimal totalReturn = totalCost.compareTo(BigDecimal.ZERO) > 0
                ? percentChange(totalValue, totalCost)
                : BigDecimal.ZERO;
        return new PortfolioTotals(
                totalValue,
                totalCost,
                totalReturn,
                weightedDailyChange(stocks, totalValue)
        );
    }

    private BigDecimal weightedDailyChange(
            List<StockHoldingResponse> stocks,
            BigDecimal currentTotal
    ) {
        if (currentTotal.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }
        BigDecimal previousTotal = stocks.stream()
                .map(stock -> previousMarketValue(
                        stock.getMarketValue(),
                        stock.getDailyChangePct()))
                .reduce(BigDecimal.ZERO, BigDecimal::add);
        return previousTotal.compareTo(BigDecimal.ZERO) == 0
                ? BigDecimal.ZERO
                : percentChange(currentTotal, previousTotal);
    }

    private BigDecimal previousMarketValue(BigDecimal currentValue, BigDecimal changePct) {
        if (changePct == null) return currentValue;
        BigDecimal multiplier = BigDecimal.ONE.add(
                changePct.divide(BigDecimal.valueOf(100), 8, RoundingMode.HALF_UP));
        return multiplier.compareTo(BigDecimal.ZERO) <= 0
                ? currentValue
                : currentValue.divide(multiplier, 8, RoundingMode.HALF_UP);
    }

    private PortfolioHistoryResponse.HistoryPoint toHistoryPoint(
            PortfolioHistory history,
            Map<LocalDate, BigDecimal> cashByDate
    ) {
        BigDecimal investedValue = history.getTotalValue();
        BigDecimal cashBalance =
                cashByDate.getOrDefault(history.getSnapshotDate(), BigDecimal.ZERO);
        BigDecimal totalAssetValue = investedValue.add(cashBalance);
        return PortfolioHistoryResponse.HistoryPoint.builder()
                .date(history.getSnapshotDate())
                .totalValue(totalAssetValue)
                .investedValue(investedValue)
                .cashBalance(cashBalance)
                .totalAssetValue(totalAssetValue)
                .totalReturnPct(history.getTotalReturnPct())
                .build();
    }

    private LocalDate startDate(String period, LocalDate end) {
        if ("all".equalsIgnoreCase(period)) {
            return LocalDate.of(1970, 1, 1);
        }
        if ("year".equalsIgnoreCase(period)) {
            return end.minusDays(365);
        }
        return end.minusDays(30);
    }

    private boolean hasPosition(UserPortfolio holding) {
        return holding.getAvgPrice() != null
                && holding.getAvgPrice().compareTo(BigDecimal.ZERO) > 0
                && holding.getQuantity() != null
                && holding.getQuantity().compareTo(BigDecimal.ZERO) > 0;
    }

    private BigDecimal percentChange(BigDecimal current, BigDecimal previous) {
        if (previous.compareTo(BigDecimal.ZERO) == 0) {
            return BigDecimal.ZERO;
        }
        return current.subtract(previous)
                .divide(previous, 4, RoundingMode.HALF_UP)
                .multiply(BigDecimal.valueOf(100));
    }

    private BigDecimal scale(BigDecimal value) {
        return value.setScale(2, RoundingMode.HALF_UP);
    }

    private record PortfolioTotals(
            BigDecimal totalValue,
            BigDecimal totalCost,
            BigDecimal totalReturnPct,
            BigDecimal dailyChangePct
    ) {
    }
}
