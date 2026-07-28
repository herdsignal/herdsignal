package com.herdsignal.service;

import com.herdsignal.domain.PortfolioLedgerEntry;
import com.herdsignal.domain.PortfolioLedgerEntryType;
import com.herdsignal.repository.PortfolioLedgerEntryRepository;
import com.herdsignal.repository.UserCashBalanceRepository;
import com.herdsignal.repository.UserCashHistoryRepository;
import com.herdsignal.repository.UserPortfolioRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class PortfolioLedgerProjectionServiceTest {

    private PortfolioSourceModeService sourceModeService;
    private PortfolioLedgerEntryRepository ledgerRepository;
    private UserPortfolioRepository portfolioRepository;
    private UserCashBalanceRepository cashBalanceRepository;
    private UserCashHistoryRepository cashHistoryRepository;
    private PortfolioLedgerProjectionService service;

    @BeforeEach
    void setUp() {
        sourceModeService = mock(PortfolioSourceModeService.class);
        ledgerRepository = mock(PortfolioLedgerEntryRepository.class);
        portfolioRepository = mock(UserPortfolioRepository.class);
        cashBalanceRepository = mock(UserCashBalanceRepository.class);
        cashHistoryRepository = mock(UserCashHistoryRepository.class);
        service = new PortfolioLedgerProjectionService(
                sourceModeService,
                ledgerRepository,
                portfolioRepository,
                cashBalanceRepository,
                cashHistoryRepository,
                new UsMarketSessionClock()
        );
    }

    @Test
    void leavesLegacyPortfolioUntouchedUntilOpeningSnapshotExists() {
        when(sourceModeService.isLedgerManaged("user-a")).thenReturn(false);

        service.synchronizeIfManaged("user-a");

        verify(ledgerRepository, never()).findByUserIdOrderByOccurredOnAscIdAsc(any());
        verify(portfolioRepository, never()).saveAll(any());
    }

    @Test
    void projectsOpenPositionsAndCashFromTheLedger() {
        when(sourceModeService.isLedgerManaged("user-a")).thenReturn(true);
        when(ledgerRepository.findByUserIdOrderByOccurredOnAscIdAsc("user-a"))
                .thenReturn(List.of(
                        entry(PortfolioLedgerEntryType.DEPOSIT, null, "1000", null, null),
                        entry(PortfolioLedgerEntryType.BUY, "NVDA", "250", "2.5", "100")
                ));
        when(portfolioRepository.findByUserId("user-a")).thenReturn(List.of());
        when(cashBalanceRepository.findByUserId("user-a")).thenReturn(Optional.empty());
        when(cashHistoryRepository.findByUserIdAndSnapshotDate(any(), any()))
                .thenReturn(Optional.empty());

        service.synchronizeIfManaged("user-a");

        verify(portfolioRepository).saveAll(any());
        verify(cashBalanceRepository).save(any());
        verify(cashHistoryRepository).save(any());
    }

    @Test
    void refusesToProjectAnAccountWithNegativeCash() {
        when(sourceModeService.isLedgerManaged("user-a")).thenReturn(true);
        when(ledgerRepository.findByUserIdOrderByOccurredOnAscIdAsc("user-a"))
                .thenReturn(List.of(
                        entry(PortfolioLedgerEntryType.DEPOSIT, null, "100", null, null),
                        entry(PortfolioLedgerEntryType.BUY, "NVDA", "250", "2.5", "100")
                ));

        assertThatThrownBy(() -> service.synchronizeIfManaged("user-a"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("음수");
        verify(portfolioRepository, never()).saveAll(any());
    }

    private PortfolioLedgerEntry entry(
            PortfolioLedgerEntryType type,
            String ticker,
            String gross,
            String quantity,
            String unitPrice
    ) {
        return PortfolioLedgerEntry.builder()
                .entryType(type)
                .ticker(ticker)
                .occurredOn(LocalDate.of(2026, 1, 2))
                .grossAmount(new BigDecimal(gross))
                .feeAmount(BigDecimal.ZERO)
                .quantity(quantity == null ? null : new BigDecimal(quantity))
                .unitPrice(unitPrice == null ? null : new BigDecimal(unitPrice))
                .build();
    }
}
