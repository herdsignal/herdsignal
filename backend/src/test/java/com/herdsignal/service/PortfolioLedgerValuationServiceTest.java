package com.herdsignal.service;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.domain.PortfolioLedgerEntry;
import com.herdsignal.domain.PortfolioLedgerEntryType;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.PortfolioLedgerEntryRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class PortfolioLedgerValuationServiceTest {

    private PortfolioLedgerEntryRepository ledgerRepository;
    private DailyPriceRepository priceRepository;
    private PortfolioLedgerValuationService service;

    @BeforeEach
    void setUp() {
        ledgerRepository = mock(PortfolioLedgerEntryRepository.class);
        priceRepository = mock(DailyPriceRepository.class);
        service = new PortfolioLedgerValuationService(ledgerRepository, priceRepository);
    }

    @Test
    void valuesRemainingLotsAgainstTheLatestClose() {
        when(ledgerRepository.findByUserIdOrderByOccurredOnAscIdAsc("user-a"))
                .thenReturn(List.of(
                        entry(1L, "DEPOSIT", null, null, "1000", "0"),
                        entry(2L, "BUY", "NVDA", "2", "200", "2"),
                        entry(3L, "BUY", "NVDA", "1", "120", "1"),
                        entry(4L, "SELL", "NVDA", "2.5", "375", "3")
                ));
        when(priceRepository.findLatestByTickers(List.of("NVDA")))
                .thenReturn(List.of(price("NVDA", "160")));

        var result = service.getSummary("user-a");

        assertThat(result.getStatus()).isEqualTo("LEDGER_READY");
        assertThat(result.getCashBalance()).isEqualByComparingTo("1049");
        assertThat(result.getMarketValue()).isEqualByComparingTo("80");
        assertThat(result.getAccountValue()).isEqualByComparingTo("1129");
        assertThat(result.getRealizedPnl()).isEqualByComparingTo("109.5");
        assertThat(result.getUnrealizedPnl()).isEqualByComparingTo("19.5");
        assertThat(result.getPositions()).singleElement().satisfies(position -> {
            assertThat(position.getAverageCost()).isEqualByComparingTo("121");
            assertThat(position.getUnrealizedReturnPct()).isEqualByComparingTo("32.2314");
        });
    }

    @Test
    void doesNotPublishPerformanceForAnInvalidLedger() {
        when(ledgerRepository.findByUserIdOrderByOccurredOnAscIdAsc("user-a"))
                .thenReturn(List.of(entry(1L, "SELL", "NVDA", "1", "100", "0")));

        var result = service.getSummary("user-a");

        assertThat(result.getStatus()).isEqualTo("INVALID_LEDGER");
        assertThat(result.getAccountValue()).isNull();
        assertThat(result.getErrors()).isNotEmpty();
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

    private DailyPrice price(String ticker, String close) {
        DailyPrice price = new DailyPrice();
        ReflectionTestUtils.setField(price, "ticker", ticker);
        ReflectionTestUtils.setField(price, "priceDate", LocalDate.of(2026, 1, 10));
        ReflectionTestUtils.setField(price, "closePrice", new BigDecimal(close));
        return price;
    }
}
