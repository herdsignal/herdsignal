package com.herdsignal.service;

import com.herdsignal.domain.PortfolioLedgerEntry;
import com.herdsignal.domain.PortfolioLedgerEntryType;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class PortfolioLedgerCalculatorTest {

    private final PortfolioLedgerCalculator calculator = new PortfolioLedgerCalculator();

    @Test
    void replaysPartialSalesWithFifoCostAndFees() {
        var result = calculator.calculate(List.of(
                entry(1L, "DEPOSIT", null, null, "1000", "0"),
                entry(2L, "BUY", "NVDA", "2", "200", "2"),
                entry(3L, "BUY", "NVDA", "1", "120", "1"),
                entry(4L, "SELL", "NVDA", "2.5", "375", "3")
        ));

        assertThat(result.errors()).isEmpty();
        assertThat(result.cashBalance()).isEqualByComparingTo("1049");
        assertThat(result.realizedPnl()).isEqualByComparingTo("109.5");
        assertThat(result.fees()).isEqualByComparingTo("6");
        assertThat(result.positions()).singleElement().satisfies(position -> {
            assertThat(position.quantity()).isEqualByComparingTo("0.5");
            assertThat(position.costBasis()).isEqualByComparingTo("60.5");
        });
    }

    @Test
    void rejectsOversellingWithoutPublishingARealizedResult() {
        var result = calculator.calculate(List.of(
                entry(1L, "BUY", "NVDA", "1", "100", "0"),
                entry(2L, "SELL", "NVDA", "2", "200", "0")
        ));

        assertThat(result.errors()).singleElement().asString().contains("초과");
        assertThat(result.realizedPnl()).isEqualByComparingTo("0");
        assertThat(result.positions()).singleElement()
                .extracting(PortfolioLedgerCalculator.OpenPosition::quantity)
                .isEqualTo(new BigDecimal("1"));
    }

    private PortfolioLedgerEntry entry(
            Long id,
            String type,
            String ticker,
            String quantity,
            String gross,
            String fee
    ) {
        return PortfolioLedgerEntry.builder()
                .id(id)
                .userId("user-a")
                .entryType(PortfolioLedgerEntryType.valueOf(type))
                .ticker(ticker)
                .occurredOn(LocalDate.of(2026, 1, Math.toIntExact(id)))
                .quantity(quantity == null ? null : new BigDecimal(quantity))
                .grossAmount(new BigDecimal(gross))
                .feeAmount(new BigDecimal(fee))
                .currency("USD")
                .source("MANUAL")
                .build();
    }
}
