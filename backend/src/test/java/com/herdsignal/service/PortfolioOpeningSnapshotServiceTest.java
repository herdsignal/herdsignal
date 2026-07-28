package com.herdsignal.service;

import com.herdsignal.domain.PortfolioLedgerEntry;
import com.herdsignal.domain.UserCashBalance;
import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.dto.PortfolioSourceReconciliationResponse;
import com.herdsignal.exception.DuplicateResourceException;
import com.herdsignal.repository.PortfolioLedgerEntryRepository;
import com.herdsignal.repository.UserCashBalanceRepository;
import com.herdsignal.repository.UserPortfolioRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class PortfolioOpeningSnapshotServiceTest {

    private UserPortfolioRepository portfolioRepository;
    private UserCashBalanceRepository cashBalanceRepository;
    private PortfolioLedgerEntryRepository ledgerRepository;
    private PortfolioSourceReconciliationService reconciliationService;
    private PortfolioOpeningSnapshotService service;

    @BeforeEach
    void setUp() {
        portfolioRepository = mock(UserPortfolioRepository.class);
        cashBalanceRepository = mock(UserCashBalanceRepository.class);
        ledgerRepository = mock(PortfolioLedgerEntryRepository.class);
        reconciliationService = mock(PortfolioSourceReconciliationService.class);
        service = new PortfolioOpeningSnapshotService(
                portfolioRepository,
                cashBalanceRepository,
                ledgerRepository,
                reconciliationService
        );
        when(ledgerRepository.findByUserIdOrderByOccurredOnAscIdAsc("user"))
                .thenReturn(List.of());
    }

    @Test
    void importsCurrentHoldingsAsExplicitOpeningSnapshot() {
        when(portfolioRepository.findByUserId("user")).thenReturn(List.of(
                holding("NVDA", "2", "100"),
                holding("TSLA", "1", "200")
        ));
        when(cashBalanceRepository.findByUserId("user")).thenReturn(Optional.of(
                UserCashBalance.builder().cashAmount(new BigDecimal("300")).build()
        ));
        PortfolioSourceReconciliationResponse matched =
                new PortfolioSourceReconciliationResponse(
                        "MATCHED", true,
                        new BigDecimal("300"), new BigDecimal("300"), BigDecimal.ZERO,
                        List.of(), List.of()
                );
        when(reconciliationService.reconcile("user")).thenReturn(matched);

        PortfolioSourceReconciliationResponse result =
                service.importCurrentSnapshot("user", LocalDate.of(2026, 7, 28));

        assertThat(result.ledgerCanBecomeSource()).isTrue();
        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<PortfolioLedgerEntry>> captor =
                ArgumentCaptor.forClass(List.class);
        verify(ledgerRepository).saveAllAndFlush(captor.capture());
        assertThat(captor.getValue()).hasSize(3);
        assertThat(captor.getValue().get(0).getGrossAmount())
                .isEqualByComparingTo("700");
        assertThat(captor.getValue())
                .allMatch(entry -> "OPENING_SNAPSHOT".equals(entry.getSource()));
    }

    @Test
    void rejectsImportWhenLedgerAlreadyContainsHistory() {
        when(ledgerRepository.findByUserIdOrderByOccurredOnAscIdAsc("user"))
                .thenReturn(List.of(PortfolioLedgerEntry.builder().id(1L).build()));

        assertThatThrownBy(() ->
                service.importCurrentSnapshot("user", LocalDate.of(2026, 7, 28)))
                .isInstanceOf(DuplicateResourceException.class);
    }

    @Test
    void rejectsIncompleteHoldingInsteadOfInventingCostBasis() {
        when(portfolioRepository.findByUserId("user")).thenReturn(List.of(
                UserPortfolio.builder()
                        .ticker("NVDA")
                        .quantity(new BigDecimal("2"))
                        .build()
        ));
        when(cashBalanceRepository.findByUserId("user")).thenReturn(Optional.empty());

        assertThatThrownBy(() ->
                service.importCurrentSnapshot("user", LocalDate.of(2026, 7, 28)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("NVDA");
    }

    private UserPortfolio holding(
            String ticker,
            String quantity,
            String averagePrice
    ) {
        return UserPortfolio.builder()
                .ticker(ticker)
                .quantity(new BigDecimal(quantity))
                .avgPrice(new BigDecimal(averagePrice))
                .build();
    }
}
