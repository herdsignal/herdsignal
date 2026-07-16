package com.herdsignal.service;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.domain.InvestorProfile;
import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.UserCashBalanceRepository;
import com.herdsignal.repository.UserPortfolioRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.stream.Collectors;

/** 실제 보유 수량·최신 종가·현금을 Action Layer용 비중으로 변환한다. */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class PortfolioActionContextService {

    private final UserPortfolioRepository portfolioRepository;
    private final UserCashBalanceRepository cashBalanceRepository;
    private final DailyPriceRepository dailyPriceRepository;

    public Map<String, PortfolioActionContext> getContexts(
            String userId,
            List<String> requestedTickers,
            InvestorProfile profile
    ) {
        if (userId == null || userId.isBlank() || requestedTickers == null || requestedTickers.isEmpty()) {
            return Map.of();
        }

        List<UserPortfolio> holdings = portfolioRepository.findByUserId(userId).stream()
                .filter(holding -> holding.getQuantity() != null
                        && holding.getQuantity().compareTo(BigDecimal.ZERO) > 0)
                .toList();
        List<String> holdingTickers = holdings.stream().map(UserPortfolio::getTicker).distinct().toList();
        if (holdingTickers.isEmpty()) {
            return Map.of();
        }

        Map<String, BigDecimal> latestPrices = dailyPriceRepository.findLatestByTickers(holdingTickers).stream()
                .filter(price -> price.getClosePrice() != null)
                .collect(Collectors.toMap(DailyPrice::getTicker, DailyPrice::getClosePrice));
        Map<String, BigDecimal> marketValues = holdings.stream()
                .filter(holding -> latestPrices.containsKey(holding.getTicker()))
                .collect(Collectors.toMap(
                        UserPortfolio::getTicker,
                        holding -> holding.getQuantity().multiply(latestPrices.get(holding.getTicker())),
                        BigDecimal::add
                ));
        BigDecimal investedValue = marketValues.values().stream()
                .reduce(BigDecimal.ZERO, BigDecimal::add);
        BigDecimal cash = cashBalanceRepository.findByUserId(userId)
                .map(balance -> balance.getCashAmount() == null ? BigDecimal.ZERO : balance.getCashAmount())
                .orElse(BigDecimal.ZERO);
        BigDecimal totalAssets = investedValue.add(cash);
        if (totalAssets.compareTo(BigDecimal.ZERO) <= 0) {
            return Map.of();
        }

        double equityRatio = ratio(investedValue, totalAssets);
        double targetEquityRatio = profile == null || profile.getTargetEquityRatio() == null
                ? 0.70
                : profile.getTargetEquityRatio().doubleValue();
        return requestedTickers.stream()
                .filter(Objects::nonNull)
                .distinct()
                .collect(Collectors.toUnmodifiableMap(
                        ticker -> ticker,
                        ticker -> new PortfolioActionContext(
                                true,
                                ratio(marketValues.getOrDefault(ticker, BigDecimal.ZERO), totalAssets),
                                equityRatio,
                                targetEquityRatio
                        )
                ));
    }

    private double ratio(BigDecimal value, BigDecimal total) {
        return value.divide(total, 8, RoundingMode.HALF_UP).doubleValue();
    }
}
