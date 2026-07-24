package com.herdsignal.service;

import com.herdsignal.domain.PortfolioHistory;
import com.herdsignal.domain.UserCashBalance;
import com.herdsignal.domain.UserCashHistory;
import com.herdsignal.dto.CashBalanceRequest;
import com.herdsignal.dto.CashBalanceResponse;
import com.herdsignal.repository.UserCashBalanceRepository;
import com.herdsignal.repository.UserCashHistoryRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 사용자의 현금 현재값과 날짜별 스냅샷 원장을 관리한다.
 */
@Service
@RequiredArgsConstructor
public class PortfolioCashService {

    private final UserCashBalanceRepository cashBalanceRepository;
    private final UserCashHistoryRepository cashHistoryRepository;
    private final UsMarketSessionClock marketSessionClock;

    @Transactional(readOnly = true)
    public CashBalanceResponse getBalance(String userId) {
        BigDecimal cashAmount = currentAmount(userId);
        LocalDate snapshotDate = cashHistoryRepository.findTopByUserIdOrderBySnapshotDateDesc(userId)
                .map(UserCashHistory::getSnapshotDate)
                .orElse(null);

        return CashBalanceResponse.builder()
                .cashAmount(cashAmount.setScale(2, RoundingMode.HALF_UP))
                .snapshotDate(snapshotDate)
                .build();
    }

    @Transactional
    public CashBalanceResponse updateBalance(String userId, CashBalanceRequest request) {
        if (request.getCashAmount() == null || request.getCashAmount().compareTo(BigDecimal.ZERO) < 0) {
            throw new IllegalArgumentException("현금 보유액은 0 이상이어야 합니다.");
        }

        BigDecimal cashAmount = request.getCashAmount().setScale(2, RoundingMode.HALF_UP);
        LocalDate snapshotDate = marketSessionClock.currentSessionDate();
        LocalDateTime now = LocalDateTime.now();

        UserCashBalance balance = cashBalanceRepository.findByUserId(userId)
                .orElseGet(() -> UserCashBalance.builder()
                        .userId(userId)
                        .cashAmount(BigDecimal.ZERO)
                        .createdAt(now)
                        .updatedAt(now)
                        .build());
        balance.setCashAmount(cashAmount);
        balance.setUpdatedAt(now);
        cashBalanceRepository.save(balance);

        UserCashHistory history = cashHistoryRepository.findByUserIdAndSnapshotDate(userId, snapshotDate)
                .orElseGet(() -> UserCashHistory.builder()
                        .userId(userId)
                        .snapshotDate(snapshotDate)
                        .cashAmount(BigDecimal.ZERO)
                        .createdAt(now)
                        .updatedAt(now)
                        .build());
        history.setCashAmount(cashAmount);
        history.setUpdatedAt(now);
        cashHistoryRepository.save(history);

        return CashBalanceResponse.builder()
                .cashAmount(cashAmount)
                .snapshotDate(snapshotDate)
                .build();
    }

    @Transactional(readOnly = true)
    public BigDecimal currentAmount(String userId) {
        return cashBalanceRepository.findByUserId(userId)
                .map(UserCashBalance::getCashAmount)
                .orElse(BigDecimal.ZERO);
    }

    @Transactional(readOnly = true)
    public Map<LocalDate, BigDecimal> historyAtPortfolioDates(
            String userId,
            LocalDate start,
            LocalDate end,
            List<PortfolioHistory> portfolioHistories
    ) {
        List<UserCashHistory> cashRows = cashHistoryRepository
                .findByUserIdAndSnapshotDateBetweenOrderBySnapshotDateAsc(userId, start, end);
        Map<LocalDate, BigDecimal> cashByDate = new HashMap<>();
        BigDecimal currentCash = cashHistoryRepository
                .findTopByUserIdAndSnapshotDateBeforeOrderBySnapshotDateDesc(userId, start)
                .map(UserCashHistory::getCashAmount)
                .orElse(BigDecimal.ZERO);

        int cashIndex = 0;
        for (PortfolioHistory portfolioHistory : portfolioHistories) {
            LocalDate date = portfolioHistory.getSnapshotDate();
            while (cashIndex < cashRows.size()
                    && !cashRows.get(cashIndex).getSnapshotDate().isAfter(date)) {
                currentCash = cashRows.get(cashIndex).getCashAmount();
                cashIndex++;
            }
            cashByDate.put(date, currentCash);
        }
        return cashByDate;
    }
}
