package com.herdsignal.service;

import com.herdsignal.domain.PortfolioLedgerEntry;
import com.herdsignal.domain.PortfolioLedgerEntryType;
import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.dto.PortfolioSourceReconciliationResponse;
import com.herdsignal.exception.DuplicateResourceException;
import com.herdsignal.repository.PortfolioLedgerEntryRepository;
import com.herdsignal.repository.UserCashBalanceRepository;
import com.herdsignal.repository.UserPortfolioRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

@Service
@RequiredArgsConstructor
public class PortfolioOpeningSnapshotService {

    private static final BigDecimal ZERO = BigDecimal.ZERO;
    private static final String SOURCE = "OPENING_SNAPSHOT";

    private final UserPortfolioRepository portfolioRepository;
    private final UserCashBalanceRepository cashBalanceRepository;
    private final PortfolioLedgerEntryRepository ledgerRepository;
    private final PortfolioSourceReconciliationService reconciliationService;

    @Transactional
    public PortfolioSourceReconciliationResponse importCurrentSnapshot(
            String userId,
            LocalDate occurredOn
    ) {
        validateDate(occurredOn);
        if (!ledgerRepository.findByUserIdOrderByOccurredOnAscIdAsc(userId).isEmpty()) {
            throw new DuplicateResourceException(
                    "원장에 항목이 있어 기초 자산을 자동으로 가져올 수 없습니다."
            );
        }

        List<UserPortfolio> holdings = portfolioRepository.findByUserId(userId).stream()
                .sorted(Comparator.comparing(UserPortfolio::getTicker))
                .toList();
        validateHoldings(holdings);
        BigDecimal cash = cashBalanceRepository.findByUserId(userId)
                .map(balance -> balance.getCashAmount() == null ? ZERO : balance.getCashAmount())
                .orElse(ZERO);
        if (cash.compareTo(ZERO) < 0) {
            throw new IllegalArgumentException("기초 현금은 0 이상이어야 합니다.");
        }

        BigDecimal positionCost = holdings.stream()
                .map(this::costBasis)
                .reduce(ZERO, BigDecimal::add);
        BigDecimal openingCapital = positionCost.add(cash).setScale(2, RoundingMode.HALF_UP);
        if (openingCapital.compareTo(ZERO) <= 0) {
            throw new IllegalArgumentException("가져올 보유 종목이나 현금이 없습니다.");
        }

        LocalDateTime now = LocalDateTime.now();
        List<PortfolioLedgerEntry> entries = new ArrayList<>();
        entries.add(PortfolioLedgerEntry.builder()
                .userId(userId)
                .entryType(PortfolioLedgerEntryType.DEPOSIT)
                .occurredOn(occurredOn)
                .grossAmount(openingCapital)
                .feeAmount(ZERO.setScale(2))
                .currency("USD")
                .source(SOURCE)
                .note("기초 자산 총액")
                .createdAt(now)
                .build());
        for (UserPortfolio holding : holdings) {
            BigDecimal quantity = holding.getQuantity().setScale(6, RoundingMode.HALF_UP);
            BigDecimal unitPrice = holding.getAvgPrice().setScale(6, RoundingMode.HALF_UP);
            entries.add(PortfolioLedgerEntry.builder()
                    .userId(userId)
                    .entryType(PortfolioLedgerEntryType.BUY)
                    .ticker(holding.getTicker())
                    .occurredOn(occurredOn)
                    .quantity(quantity)
                    .unitPrice(unitPrice)
                    .grossAmount(quantity.multiply(unitPrice).setScale(2, RoundingMode.HALF_UP))
                    .feeAmount(ZERO.setScale(2))
                    .currency("USD")
                    .source(SOURCE)
                    .note("기초 보유 스냅샷")
                    .createdAt(now)
                    .build());
        }
        ledgerRepository.saveAllAndFlush(entries);

        PortfolioSourceReconciliationResponse result =
                reconciliationService.reconcile(userId);
        if (!result.ledgerCanBecomeSource()) {
            throw new IllegalStateException(
                    "기초 자산을 저장했지만 현재 보유 현황과 일치하지 않습니다."
            );
        }
        return result;
    }

    private void validateDate(LocalDate date) {
        if (date == null) throw new IllegalArgumentException("기초 자산 기준일은 필수입니다.");
        if (date.isAfter(LocalDate.now())) {
            throw new IllegalArgumentException("미래 날짜를 기초 자산 기준일로 사용할 수 없습니다.");
        }
    }

    private void validateHoldings(List<UserPortfolio> holdings) {
        List<String> invalid = holdings.stream()
                .filter(holding -> holding.getTicker() == null
                        || holding.getAvgPrice() == null
                        || holding.getAvgPrice().compareTo(ZERO) <= 0
                        || holding.getQuantity() == null
                        || holding.getQuantity().compareTo(ZERO) <= 0)
                .map(holding -> holding.getTicker() == null ? "티커 없음" : holding.getTicker())
                .toList();
        if (!invalid.isEmpty()) {
            throw new IllegalArgumentException(
                    "수량과 평균 매수가를 먼저 확인하세요: " + String.join(", ", invalid)
            );
        }
    }

    private BigDecimal costBasis(UserPortfolio holding) {
        return holding.getQuantity().multiply(holding.getAvgPrice());
    }
}
