package com.herdsignal.service;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.domain.InvestorProfile;
import com.herdsignal.domain.UserCashBalance;
import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.UserCashBalanceRepository;
import com.herdsignal.repository.UserPortfolioRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class PortfolioActionContextServiceTest {

    private UserPortfolioRepository portfolioRepository;
    private UserCashBalanceRepository cashRepository;
    private DailyPriceRepository priceRepository;
    private PortfolioActionContextService service;

    @BeforeEach
    void setUp() {
        portfolioRepository = mock(UserPortfolioRepository.class);
        cashRepository = mock(UserCashBalanceRepository.class);
        priceRepository = mock(DailyPriceRepository.class);
        service = new PortfolioActionContextService(
                portfolioRepository, cashRepository, priceRepository);
    }

    @Test
    void calculatesTickerAndEquityWeightFromLatestPricesAndCash() {
        when(portfolioRepository.findByUserId("user-1")).thenReturn(List.of(
                holding("NVDA", "2"),
                holding("SPY", "1")
        ));
        DailyPrice nvdaPrice = price("NVDA", "200");
        DailyPrice spyPrice = price("SPY", "500");
        when(priceRepository.findLatestByTickers(List.of("NVDA", "SPY")))
                .thenReturn(List.of(nvdaPrice, spyPrice));
        when(cashRepository.findByUserId("user-1")).thenReturn(Optional.of(
                UserCashBalance.builder().cashAmount(new BigDecimal("100")).build()));
        InvestorProfile profile = InvestorProfile.builder()
                .targetEquityRatio(new BigDecimal("0.70"))
                .build();

        Map<String, PortfolioActionContext> contexts = service.getContexts(
                "user-1", List.of("NVDA", "SPY"), profile);

        assertThat(contexts.get("NVDA").currentTickerWeight()).isEqualTo(0.4);
        assertThat(contexts.get("NVDA").currentEquityRatio()).isEqualTo(0.9);
        assertThat(contexts.get("NVDA").targetEquityRatio()).isEqualTo(0.7);
    }

    private UserPortfolio holding(String ticker, String quantity) {
        return UserPortfolio.builder()
                .ticker(ticker)
                .quantity(new BigDecimal(quantity))
                .build();
    }

    private DailyPrice price(String ticker, String close) {
        DailyPrice price = mock(DailyPrice.class);
        when(price.getTicker()).thenReturn(ticker);
        when(price.getClosePrice()).thenReturn(new BigDecimal(close));
        return price;
    }
}
