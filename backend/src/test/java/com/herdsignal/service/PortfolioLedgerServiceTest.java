package com.herdsignal.service;

import com.herdsignal.domain.PortfolioLedgerEntry;
import com.herdsignal.dto.PortfolioLedgerEntryRequest;
import com.herdsignal.exception.ResourceNotFoundException;
import com.herdsignal.repository.PortfolioLedgerEntryRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.Optional;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class PortfolioLedgerServiceTest {

    private PortfolioLedgerEntryRepository repository;
    private PortfolioLedgerService service;

    @BeforeEach
    void setUp() {
        repository = mock(PortfolioLedgerEntryRepository.class);
        service = new PortfolioLedgerService(repository, new TickerSymbolPolicy());
    }

    @Test
    void derivesTradeGrossAndCashEffectOnTheServer() {
        PortfolioLedgerEntryRequest request = request("BUY", "nvda");
        ReflectionTestUtils.setField(request, "quantity", new BigDecimal("2.5"));
        ReflectionTestUtils.setField(request, "unitPrice", new BigDecimal("100"));
        ReflectionTestUtils.setField(request, "fee", new BigDecimal("1.25"));
        when(repository.save(any(PortfolioLedgerEntry.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        var response = service.create("user-a", request);

        assertThat(response.getTicker()).isEqualTo("NVDA");
        assertThat(response.getGrossAmount()).isEqualByComparingTo("250.00");
        assertThat(response.getCashEffect()).isEqualByComparingTo("-251.25");
    }

    @Test
    void requiresAnAmountForCashFlowEntriesAndRejectsTradeFieldsAsAuthority() {
        PortfolioLedgerEntryRequest request = request("DEPOSIT", null);

        assertThatThrownBy(() -> service.create("user-a", request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("금액");
        verify(repository, never()).save(any());
    }

    @Test
    void rejectsATickerOnAccountLevelCashFlows() {
        PortfolioLedgerEntryRequest request = request("DEPOSIT", "NVDA");
        ReflectionTestUtils.setField(request, "amount", new BigDecimal("100"));

        assertThatThrownBy(() -> service.create("user-a", request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("종목");
        verify(repository, never()).save(any());
    }

    @Test
    void cannotDeleteAnotherUsersEntry() {
        when(repository.findByIdAndUserId(4L, "user-b")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.delete("user-b", 4L))
                .isInstanceOf(ResourceNotFoundException.class);
        verify(repository, never()).delete(any());
    }

    @Test
    void storesAStockSplitWithoutCreatingCashFlow() {
        PortfolioLedgerEntryRequest request = request("SPLIT", "NVDA");
        ReflectionTestUtils.setField(request, "splitRatio", new BigDecimal("10"));
        when(repository.save(any(PortfolioLedgerEntry.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        var response = service.create("user-a", request);

        assertThat(response.getSplitRatio()).isEqualByComparingTo("10");
        assertThat(response.getGrossAmount()).isEqualByComparingTo("0");
        assertThat(response.getCashEffect()).isEqualByComparingTo("0");
    }

    @Test
    void exportsCsvWithEscapedNotes() {
        when(repository.findByUserIdOrderByOccurredOnAscIdAsc("user-a")).thenReturn(List.of(
                PortfolioLedgerEntry.builder()
                        .entryType(com.herdsignal.domain.PortfolioLedgerEntryType.DEPOSIT)
                        .occurredOn(LocalDate.of(2026, 1, 2))
                        .grossAmount(new BigDecimal("500"))
                        .feeAmount(BigDecimal.ZERO)
                        .currency("USD")
                        .note("첫 입금, 시작")
                        .build()
        ));

        String csv = service.exportCsv("user-a");

        assertThat(csv).startsWith("date,type,ticker");
        assertThat(csv).contains("\"첫 입금, 시작\"");
    }

    private PortfolioLedgerEntryRequest request(String type, String ticker) {
        PortfolioLedgerEntryRequest request = new PortfolioLedgerEntryRequest();
        ReflectionTestUtils.setField(request, "entryType", type);
        ReflectionTestUtils.setField(request, "ticker", ticker);
        ReflectionTestUtils.setField(request, "occurredOn", LocalDate.of(2026, 1, 2));
        return request;
    }
}
