package com.herdsignal.service;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.dto.PortfolioSummaryResponse;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.PortfolioHistoryRepository;
import com.herdsignal.repository.UserCashBalanceRepository;
import com.herdsignal.repository.UserCashHistoryRepository;
import com.herdsignal.repository.UserPortfolioRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class PortfolioServiceTest {

    private UserPortfolioRepository portfolioRepository;
    private PortfolioHistoryRepository historyRepository;
    private DailyPriceRepository dailyPriceRepository;
    private UserCashBalanceRepository cashBalanceRepository;
    private PortfolioService portfolioService;

    @BeforeEach
    void setUp() {
        portfolioRepository = mock(UserPortfolioRepository.class);
        historyRepository = mock(PortfolioHistoryRepository.class);
        dailyPriceRepository = mock(DailyPriceRepository.class);
        cashBalanceRepository = mock(UserCashBalanceRepository.class);
        portfolioService = new PortfolioService(
                portfolioRepository,
                historyRepository,
                dailyPriceRepository,
                mock(TickerReadinessService.class),
                cashBalanceRepository,
                mock(UserCashHistoryRepository.class)
        );

        when(historyRepository.findTopByUserIdOrderBySnapshotDateDesc(anyString()))
                .thenReturn(Optional.empty());
        when(cashBalanceRepository.findByUserId(anyString())).thenReturn(Optional.empty());
    }

    @Test
    void returnsPriceDateAndCalculatesDailyChangeFromPreviousTradingDay() {
        DailyPrice currentPrice = price(LocalDate.now(), "110");
        DailyPrice previousPrice = price(LocalDate.now().minusDays(3), "100");
        when(portfolioRepository.findByUserId("user-1"))
                .thenReturn(List.of(holding("NVDA")));
        when(dailyPriceRepository
                .findTopByTickerAndPriceDateLessThanEqualAndClosePriceIsNotNullOrderByPriceDateDesc(
                        anyString(), any(LocalDate.class)))
                .thenReturn(Optional.of(currentPrice));
        when(dailyPriceRepository
                .findTopByTickerAndPriceDateLessThanAndClosePriceIsNotNullOrderByPriceDateDesc(
                        "NVDA", LocalDate.now()))
                .thenReturn(Optional.of(previousPrice));

        PortfolioSummaryResponse response = portfolioService.getPortfolioSummary("user-1");

        assertThat(response.getStocks()).hasSize(1);
        assertThat(response.getStocks().get(0).getPriceDate()).isEqualTo(LocalDate.now());
        assertThat(response.getStocks().get(0).getDailyChangePct()).isEqualByComparingTo("10.00");
        assertThat(response.getMarketDataDate()).isEqualTo(LocalDate.now());
    }

    @Test
    void usesOldestStockDateAsConservativeMarketDataDate() {
        DailyPrice nvdaPrice = price(LocalDate.now(), "100");
        DailyPrice tslaPrice = price(LocalDate.now().minusDays(1), "100");
        when(portfolioRepository.findByUserId("user-1"))
                .thenReturn(List.of(holding("NVDA"), holding("TSLA")));
        when(dailyPriceRepository
                .findTopByTickerAndPriceDateLessThanEqualAndClosePriceIsNotNullOrderByPriceDateDesc(
                        anyString(), any(LocalDate.class)))
                .thenAnswer(invocation -> {
                    String ticker = invocation.getArgument(0);
                    return Optional.of(ticker.equals("NVDA") ? nvdaPrice : tslaPrice);
                });

        PortfolioSummaryResponse response = portfolioService.getPortfolioSummary("user-1");

        assertThat(response.getMarketDataDate()).isEqualTo(LocalDate.now().minusDays(1));
    }

    private UserPortfolio holding(String ticker) {
        return UserPortfolio.builder()
                .userId("user-1")
                .ticker(ticker)
                .avgPrice(new BigDecimal("90"))
                .quantity(BigDecimal.ONE)
                .build();
    }

    private DailyPrice price(LocalDate date, String close) {
        DailyPrice price = mock(DailyPrice.class);
        when(price.getPriceDate()).thenReturn(date);
        when(price.getClosePrice()).thenReturn(new BigDecimal(close));
        return price;
    }
}
