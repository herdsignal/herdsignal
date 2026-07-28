package com.herdsignal.service;

import com.herdsignal.domain.PortfolioLedgerEntry;
import com.herdsignal.domain.UserCashBalance;
import com.herdsignal.domain.UserCashHistory;
import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.repository.PortfolioLedgerEntryRepository;
import com.herdsignal.repository.UserCashBalanceRepository;
import com.herdsignal.repository.UserCashHistoryRepository;
import com.herdsignal.repository.UserPortfolioRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class PortfolioLedgerProjectionService {

    private final PortfolioSourceModeService sourceModeService;
    private final PortfolioLedgerEntryRepository ledgerRepository;
    private final UserPortfolioRepository portfolioRepository;
    private final UserCashBalanceRepository cashBalanceRepository;
    private final UserCashHistoryRepository cashHistoryRepository;
    private final UsMarketSessionClock marketSessionClock;

    @Transactional
    public void synchronizeIfManaged(String userId) {
        if (!sourceModeService.isLedgerManaged(userId)) return;

        List<PortfolioLedgerEntry> entries =
                ledgerRepository.findByUserIdOrderByOccurredOnAscIdAsc(userId);
        PortfolioLedgerCalculator.Calculation calculation =
                new PortfolioLedgerCalculator().calculate(entries);
        if (!calculation.errors().isEmpty()) {
            throw new IllegalArgumentException(
                    "원장 계산 오류로 보유 현황을 갱신하지 않았습니다: "
                            + String.join("; ", calculation.errors())
            );
        }
        if (calculation.cashBalance().compareTo(BigDecimal.ZERO) < 0) {
            throw new IllegalArgumentException(
                    "원장 현금 잔액이 음수입니다. 입금 또는 거래 내역을 먼저 확인해주세요."
            );
        }

        LocalDateTime now = LocalDateTime.now();
        Map<String, UserPortfolio> existing = portfolioRepository.findByUserId(userId)
                .stream()
                .collect(Collectors.toMap(UserPortfolio::getTicker, Function.identity()));
        List<UserPortfolio> projected = calculation.positions().stream()
                .map(position -> projectPosition(userId, position, existing.remove(position.ticker()), now))
                .toList();
        portfolioRepository.saveAll(projected);
        if (!existing.isEmpty()) {
            portfolioRepository.deleteAll(existing.values());
        }
        projectCash(userId, calculation.cashBalance(), now);
    }

    private UserPortfolio projectPosition(
            String userId,
            PortfolioLedgerCalculator.OpenPosition position,
            UserPortfolio current,
            LocalDateTime now
    ) {
        UserPortfolio holding = current == null
                ? UserPortfolio.builder()
                        .userId(userId)
                        .ticker(position.ticker())
                        .createdAt(now)
                        .build()
                : current;
        holding.setQuantity(position.quantity().setScale(6, RoundingMode.HALF_UP));
        holding.setAvgPrice(position.costBasis()
                .divide(position.quantity(), 6, RoundingMode.HALF_UP));
        holding.setUpdatedAt(now);
        return holding;
    }

    private void projectCash(String userId, BigDecimal amount, LocalDateTime now) {
        BigDecimal cash = amount.setScale(2, RoundingMode.HALF_UP);
        UserCashBalance balance = cashBalanceRepository.findByUserId(userId)
                .orElseGet(() -> UserCashBalance.builder()
                        .userId(userId)
                        .createdAt(now)
                        .build());
        balance.setCashAmount(cash);
        balance.setUpdatedAt(now);
        cashBalanceRepository.save(balance);

        LocalDate sessionDate = marketSessionClock.currentSessionDate();
        UserCashHistory history = cashHistoryRepository
                .findByUserIdAndSnapshotDate(userId, sessionDate)
                .orElseGet(() -> UserCashHistory.builder()
                        .userId(userId)
                        .snapshotDate(sessionDate)
                        .createdAt(now)
                        .build());
        history.setCashAmount(cash);
        history.setUpdatedAt(now);
        cashHistoryRepository.save(history);
    }
}
