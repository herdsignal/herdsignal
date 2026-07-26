package com.herdsignal.service;

import com.herdsignal.domain.PortfolioLedgerEntry;
import com.herdsignal.domain.PortfolioLedgerEntryType;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class PortfolioTwrCalculatorTest {

    @Test
    void removesDepositsFromReturnAndMatchesCashFlowsToSpy() {
        LocalDate first = LocalDate.of(2026, 1, 2);
        LocalDate second = LocalDate.of(2026, 1, 5);
        LocalDate third = LocalDate.of(2026, 1, 6);
        var result = new PortfolioTwrCalculator().calculate(
                List.of(
                        entry(1L, "DEPOSIT", first, null, null, "1000"),
                        entry(2L, "BUY", first, "NVDA", "10", "1000"),
                        entry(3L, "DEPOSIT", third, null, null, "500")
                ),
                closes(
                        first, "100", "100",
                        second, "110", "105",
                        third, "121", "110.25"
                ),
                "SPY"
        );

        assertThat(result.status()).isEqualTo("PERFORMANCE_READY");
        assertThat(result.portfolioReturnPct()).isEqualByComparingTo("21");
        assertThat(result.benchmarkReturnPct()).isEqualByComparingTo("10.25");
        assertThat(result.points()).hasSize(3);
    }

    @Test
    void failsClosedWhenAHeldTickerPriceIsMissing() {
        LocalDate first = LocalDate.of(2026, 1, 2);
        LocalDate second = LocalDate.of(2026, 1, 5);
        Map<LocalDate, Map<String, BigDecimal>> prices = new LinkedHashMap<>();
        prices.put(first, Map.of("NVDA", new BigDecimal("100"), "SPY", new BigDecimal("100")));
        prices.put(second, Map.of("SPY", new BigDecimal("101")));

        var result = new PortfolioTwrCalculator().calculate(
                List.of(
                        entry(1L, "DEPOSIT", first, null, null, "1000"),
                        entry(2L, "BUY", first, "NVDA", "10", "1000")
                ),
                prices,
                "SPY"
        );

        assertThat(result.status()).isEqualTo("INVALID_PERFORMANCE_INPUT");
        assertThat(result.errors()).singleElement().asString().contains("종가");
    }

    private Map<LocalDate, Map<String, BigDecimal>> closes(
            LocalDate first, String nvda1, String spy1,
            LocalDate second, String nvda2, String spy2,
            LocalDate third, String nvda3, String spy3
    ) {
        Map<LocalDate, Map<String, BigDecimal>> prices = new LinkedHashMap<>();
        prices.put(first, Map.of("NVDA", new BigDecimal(nvda1), "SPY", new BigDecimal(spy1)));
        prices.put(second, Map.of("NVDA", new BigDecimal(nvda2), "SPY", new BigDecimal(spy2)));
        prices.put(third, Map.of("NVDA", new BigDecimal(nvda3), "SPY", new BigDecimal(spy3)));
        return prices;
    }

    private PortfolioLedgerEntry entry(
            Long id,
            String type,
            LocalDate date,
            String ticker,
            String quantity,
            String gross
    ) {
        return PortfolioLedgerEntry.builder()
                .id(id)
                .entryType(PortfolioLedgerEntryType.valueOf(type))
                .occurredOn(date)
                .ticker(ticker)
                .quantity(quantity == null ? null : new BigDecimal(quantity))
                .grossAmount(new BigDecimal(gross))
                .feeAmount(BigDecimal.ZERO)
                .build();
    }
}
