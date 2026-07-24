package com.herdsignal.dto;

import jakarta.validation.Validation;
import jakarta.validation.Validator;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;

class RequestValidationTest {
    private final Validator validator =
            Validation.buildDefaultValidatorFactory().getValidator();

    @Test
    void rejectsMissingOrUnsafePortfolioTicker() {
        PortfolioAddRequest missing = new PortfolioAddRequest();
        PortfolioAddRequest unsafe = new PortfolioAddRequest();
        ReflectionTestUtils.setField(unsafe, "ticker", "NVDA;DROP");

        assertThat(validator.validate(missing)).isNotEmpty();
        assertThat(validator.validate(unsafe)).isNotEmpty();
    }

    @Test
    void rejectsNonPositiveHoldingValues() {
        AvgPriceUpdateRequest request = new AvgPriceUpdateRequest();
        ReflectionTestUtils.setField(request, "avgPrice", BigDecimal.ZERO);
        ReflectionTestUtils.setField(request, "quantity", new BigDecimal("-1"));

        assertThat(validator.validate(request)).hasSize(2);
    }

    @Test
    void rejectsTextThatWouldOverflowDatabaseColumns() {
        WatchlistAddRequest request = new WatchlistAddRequest();
        ReflectionTestUtils.setField(request, "ticker", "NVDA");
        ReflectionTestUtils.setField(request, "memo", "x".repeat(201));

        assertThat(validator.validate(request))
                .anyMatch(error -> error.getPropertyPath().toString().equals("memo"));
    }

    @Test
    void acceptsValidRebalanceSettings() {
        RebalanceSettingsRequest request = new RebalanceSettingsRequest(
                new BigDecimal("1000"),
                new BigDecimal("0.10"),
                "STANDARD"
        );

        assertThat(validator.validate(request)).isEmpty();
    }
}
