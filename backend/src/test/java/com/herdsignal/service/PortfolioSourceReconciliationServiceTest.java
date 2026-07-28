package com.herdsignal.service;

import com.herdsignal.domain.PortfolioLedgerEntry;
import com.herdsignal.domain.PortfolioLedgerEntryType;
import com.herdsignal.domain.UserCashBalance;
import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.dto.PortfolioSourceReconciliationResponse;
import com.herdsignal.repository.PortfolioLedgerEntryRepository;
import com.herdsignal.repository.UserCashBalanceRepository;
import com.herdsignal.repository.UserPortfolioRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class PortfolioSourceReconciliationServiceTest {

    private UserPortfolioRepository portfolioRepository;
    private UserCashBalanceRepository cashBalanceRepository;
    private PortfolioLedgerEntryRepository ledgerRepository;
    private PortfolioSourceReconciliationService service;

    @BeforeEach
    void setUp() {
        portfolioRepository = mock(UserPortfolioRepository.class);
        cashBalanceRepository = mock(UserCashBalanceRepository.class);
        ledgerRepository = mock(PortfolioLedgerEntryRepository.class);
        service = new PortfolioSourceReconciliationService(
                portfolioRepository,
                cashBalanceRepository,
                ledgerRepository
        );
        when(portfolioRepository.findByUserId("user")).thenReturn(List.of());
        when(cashBalanceRepository.findByUserId("user")).thenReturn(Optional.empty());
    }

    @Test
    void blocksPromotionWhenLedgerIsEmpty() {
        when(ledgerRepository.findByUserIdOrderByOccurredOnAscIdAsc("user"))
                .thenReturn(List.of());

        PortfolioSourceReconciliationResponse result = service.reconcile("user");

        assertThat(result.status()).isEqualTo("NO_LEDGER");
        assertThat(result.ledgerCanBecomeSource()).isFalse();
    }

    @Test
    void reportsMatchedOnlyWhenPositionsAndCashAgree() {
        when(ledgerRepository.existsByUserIdAndSource("user", "OPENING_SNAPSHOT"))
                .thenReturn(true);
        when(ledgerRepository.findByUserIdOrderByOccurredOnAscIdAsc("user"))
                .thenReturn(List.of(
                        cashEntry(PortfolioLedgerEntryType.DEPOSIT, "1000"),
                        buyEntry("NVDA", "2", "100")
                ));
        when(portfolioRepository.findByUserId("user"))
                .thenReturn(List.of(holding("NVDA", "2")));
        when(cashBalanceRepository.findByUserId("user"))
                .thenReturn(Optional.of(UserCashBalance.builder()
                        .cashAmount(new BigDecimal("800"))
                        .build()));

        PortfolioSourceReconciliationResponse result = service.reconcile("user");

        assertThat(result.status()).isEqualTo("MATCHED");
        assertThat(result.ledgerManaged()).isTrue();
        assertThat(result.ledgerCanBecomeSource()).isTrue();
        assertThat(result.positionDifferences()).isEmpty();
        assertThat(result.cashDifference()).isEqualByComparingTo("0");
    }

    @Test
    void exposesDifferencesWithoutMutatingEitherSource() {
        when(ledgerRepository.findByUserIdOrderByOccurredOnAscIdAsc("user"))
                .thenReturn(List.of(
                        cashEntry(PortfolioLedgerEntryType.DEPOSIT, "1000"),
                        buyEntry("NVDA", "2", "100")
                ));
        when(portfolioRepository.findByUserId("user"))
                .thenReturn(List.of(holding("NVDA", "1"), holding("TSLA", "3")));
        when(cashBalanceRepository.findByUserId("user"))
                .thenReturn(Optional.of(UserCashBalance.builder()
                        .cashAmount(new BigDecimal("900"))
                        .build()));

        PortfolioSourceReconciliationResponse result = service.reconcile("user");

        assertThat(result.status()).isEqualTo("DIVERGED");
        assertThat(result.ledgerCanBecomeSource()).isFalse();
        assertThat(result.cashDifference()).isEqualByComparingTo("-100");
        assertThat(result.positionDifferences())
                .extracting(PortfolioSourceReconciliationResponse.PositionDifference::ticker)
                .containsExactly("NVDA", "TSLA");
    }

    private UserPortfolio holding(String ticker, String quantity) {
        return UserPortfolio.builder()
                .ticker(ticker)
                .quantity(new BigDecimal(quantity))
                .build();
    }

    private PortfolioLedgerEntry cashEntry(PortfolioLedgerEntryType type, String amount) {
        return PortfolioLedgerEntry.builder()
                .id(1L)
                .entryType(type)
                .occurredOn(LocalDate.of(2026, 1, 1))
                .grossAmount(new BigDecimal(amount))
                .feeAmount(BigDecimal.ZERO)
                .build();
    }

    private PortfolioLedgerEntry buyEntry(String ticker, String quantity, String price) {
        BigDecimal parsedQuantity = new BigDecimal(quantity);
        BigDecimal parsedPrice = new BigDecimal(price);
        return PortfolioLedgerEntry.builder()
                .id(2L)
                .entryType(PortfolioLedgerEntryType.BUY)
                .ticker(ticker)
                .occurredOn(LocalDate.of(2026, 1, 2))
                .quantity(parsedQuantity)
                .unitPrice(parsedPrice)
                .grossAmount(parsedQuantity.multiply(parsedPrice))
                .feeAmount(BigDecimal.ZERO)
                .build();
    }
}
