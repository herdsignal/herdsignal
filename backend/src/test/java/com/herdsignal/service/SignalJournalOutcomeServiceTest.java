package com.herdsignal.service;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.domain.SignalJournal;
import com.herdsignal.repository.DailyPriceRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class SignalJournalOutcomeServiceTest {

    private DailyPriceRepository repository;
    private SignalJournalOutcomeService service;

    @BeforeEach
    void setUp() {
        repository = mock(DailyPriceRepository.class);
        service = new SignalJournalOutcomeService(repository);
    }

    @Test
    void calculatesFixedCalendarHorizonReturnsWithoutActionDirectionInversion() {
        SignalJournal journal = journal("NVDA", LocalDate.of(2025, 1, 2));
        DailyPrice reference = price("NVDA", LocalDate.of(2025, 1, 2), "100");
        DailyPrice month1 = price("NVDA", LocalDate.of(2025, 2, 3), "110");
        DailyPrice month3 = price("NVDA", LocalDate.of(2025, 4, 2), "90");
        DailyPrice month6 = price("NVDA", LocalDate.of(2025, 7, 2), "120");

        when(repository
                .findTopByTickerAndPriceDateBetweenAndClosePriceIsNotNullOrderByPriceDateDesc(
                        "NVDA",
                        LocalDate.of(2024, 12, 26),
                        LocalDate.of(2025, 1, 2)
                ))
                .thenReturn(Optional.of(reference));
        when(repository
                .findTopByTickerAndPriceDateBetweenAndClosePriceIsNotNullOrderByPriceDateAsc(
                        "NVDA",
                        LocalDate.of(2025, 2, 2),
                        LocalDate.of(2025, 2, 9)
                ))
                .thenReturn(Optional.of(month1));
        when(repository
                .findTopByTickerAndPriceDateBetweenAndClosePriceIsNotNullOrderByPriceDateAsc(
                        "NVDA",
                        LocalDate.of(2025, 4, 2),
                        LocalDate.of(2025, 4, 9)
                ))
                .thenReturn(Optional.of(month3));
        when(repository
                .findTopByTickerAndPriceDateBetweenAndClosePriceIsNotNullOrderByPriceDateAsc(
                        "NVDA",
                        LocalDate.of(2025, 7, 2),
                        LocalDate.of(2025, 7, 9)
                ))
                .thenReturn(Optional.of(month6));

        var result = service.evaluate(journal, LocalDate.of(2025, 7, 10));

        assertThat(result.referencePrice()).isEqualByComparingTo("100");
        assertThat(result.outcomes())
                .extracting(outcome -> outcome.getReturnPct())
                .containsExactly(
                        new BigDecimal("10.0000"),
                        new BigDecimal("-10.0000"),
                        new BigDecimal("20.0000")
                );
        assertThat(result.outcomes())
                .extracting(outcome -> outcome.getStatus())
                .containsOnly("AVAILABLE");
    }

    @Test
    void keepsHorizonsPendingUntilTheMarketDatasetReachesTheirTargetDate() {
        SignalJournal journal = journal("TSLA", LocalDate.of(2025, 1, 2));
        DailyPrice reference = price("TSLA", LocalDate.of(2025, 1, 2), "100");
        when(repository
                .findTopByTickerAndPriceDateBetweenAndClosePriceIsNotNullOrderByPriceDateDesc(
                        "TSLA",
                        LocalDate.of(2024, 12, 26),
                        LocalDate.of(2025, 1, 2)
                ))
                .thenReturn(Optional.of(reference));

        var result = service.evaluate(journal, LocalDate.of(2025, 1, 31));

        assertThat(result.outcomes())
                .extracting(outcome -> outcome.getStatus())
                .containsOnly("PENDING");
    }

    @Test
    void marksEveryHorizonUnavailableWhenTheReferenceCloseCannotBeEstablished() {
        SignalJournal journal = journal("MISSING", LocalDate.of(2025, 1, 2));
        when(repository
                .findTopByTickerAndPriceDateBetweenAndClosePriceIsNotNullOrderByPriceDateDesc(
                        "MISSING",
                        LocalDate.of(2024, 12, 26),
                        LocalDate.of(2025, 1, 2)
                ))
                .thenReturn(Optional.empty());

        var result = service.evaluate(journal, LocalDate.of(2026, 1, 2));

        assertThat(result.referencePrice()).isNull();
        assertThat(result.outcomes())
                .extracting(outcome -> outcome.getStatus())
                .containsOnly("UNAVAILABLE");
    }

    private SignalJournal journal(String ticker, LocalDate scoreDate) {
        return SignalJournal.builder()
                .ticker(ticker)
                .actionType("SELL")
                .scoreDate(scoreDate)
                .recordedAt(LocalDateTime.of(scoreDate, java.time.LocalTime.NOON))
                .build();
    }

    private DailyPrice price(String ticker, LocalDate date, String close) {
        DailyPrice price = new DailyPrice();
        ReflectionTestUtils.setField(price, "ticker", ticker);
        ReflectionTestUtils.setField(price, "priceDate", date);
        ReflectionTestUtils.setField(price, "closePrice", new BigDecimal(close));
        return price;
    }
}
