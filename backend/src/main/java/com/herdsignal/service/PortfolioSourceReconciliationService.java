package com.herdsignal.service;

import com.herdsignal.domain.PortfolioLedgerEntry;
import com.herdsignal.domain.UserPortfolio;
import com.herdsignal.dto.PortfolioSourceReconciliationResponse;
import com.herdsignal.repository.PortfolioLedgerEntryRepository;
import com.herdsignal.repository.UserCashBalanceRepository;
import com.herdsignal.repository.UserPortfolioRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class PortfolioSourceReconciliationService {

    private static final BigDecimal ZERO = BigDecimal.ZERO;

    private final UserPortfolioRepository portfolioRepository;
    private final UserCashBalanceRepository cashBalanceRepository;
    private final PortfolioLedgerEntryRepository ledgerRepository;

    @Transactional(readOnly = true)
    public PortfolioSourceReconciliationResponse reconcile(String userId) {
        boolean ledgerManaged = ledgerRepository.existsByUserIdAndSource(
                userId,
                PortfolioSourceModeService.OPENING_SNAPSHOT_SOURCE
        );
        List<PortfolioLedgerEntry> entries =
                ledgerRepository.findByUserIdOrderByOccurredOnAscIdAsc(userId);
        BigDecimal manualCash = cashBalanceRepository.findByUserId(userId)
                .map(balance -> valueOrZero(balance.getCashAmount()))
                .orElse(ZERO);

        if (entries.isEmpty()) {
            return response(
                    "NO_LEDGER",
                    ledgerManaged,
                    false,
                    manualCash,
                    ZERO,
                    List.of(),
                    List.of()
            );
        }

        PortfolioLedgerCalculator.Calculation calculation =
                new PortfolioLedgerCalculator().calculate(entries);
        if (!calculation.errors().isEmpty()) {
            return response(
                    "LEDGER_INVALID",
                    ledgerManaged,
                    false,
                    manualCash,
                    calculation.cashBalance(),
                    List.of(),
                    calculation.errors()
            );
        }

        Map<String, BigDecimal> manual = portfolioRepository.findByUserId(userId).stream()
                .collect(Collectors.toMap(
                        UserPortfolio::getTicker,
                        holding -> valueOrZero(holding.getQuantity()),
                        BigDecimal::add
                ));
        Map<String, BigDecimal> ledger = calculation.positions().stream()
                .collect(Collectors.toMap(
                        PortfolioLedgerCalculator.OpenPosition::ticker,
                        PortfolioLedgerCalculator.OpenPosition::quantity
                ));

        List<PortfolioSourceReconciliationResponse.PositionDifference> differences =
                positionDifferences(manual, ledger);
        BigDecimal ledgerCash = calculation.cashBalance();
        boolean cashMatches = manualCash.compareTo(ledgerCash) == 0;
        boolean matched = cashMatches && differences.isEmpty();

        return response(
                matched ? "MATCHED" : "DIVERGED",
                ledgerManaged,
                matched,
                manualCash,
                ledgerCash,
                differences,
                List.of()
        );
    }

    private List<PortfolioSourceReconciliationResponse.PositionDifference> positionDifferences(
            Map<String, BigDecimal> manual,
            Map<String, BigDecimal> ledger
    ) {
        TreeSet<String> tickers = new TreeSet<>();
        tickers.addAll(manual.keySet());
        tickers.addAll(ledger.keySet());

        List<PortfolioSourceReconciliationResponse.PositionDifference> differences =
                new ArrayList<>();
        for (String ticker : tickers) {
            BigDecimal manualQuantity = manual.getOrDefault(ticker, ZERO);
            BigDecimal ledgerQuantity = ledger.getOrDefault(ticker, ZERO);
            if (manualQuantity.compareTo(ledgerQuantity) == 0) continue;
            differences.add(new PortfolioSourceReconciliationResponse.PositionDifference(
                    ticker,
                    manualQuantity,
                    ledgerQuantity,
                    ledgerQuantity.subtract(manualQuantity)
            ));
        }
        return List.copyOf(differences);
    }

    private PortfolioSourceReconciliationResponse response(
            String status,
            boolean ledgerManaged,
            boolean canPromote,
            BigDecimal manualCash,
            BigDecimal ledgerCash,
            List<PortfolioSourceReconciliationResponse.PositionDifference> differences,
            List<String> errors
    ) {
        return new PortfolioSourceReconciliationResponse(
                status,
                ledgerManaged,
                canPromote,
                manualCash,
                ledgerCash,
                ledgerCash.subtract(manualCash),
                differences,
                List.copyOf(errors)
        );
    }

    private BigDecimal valueOrZero(BigDecimal value) {
        return value == null ? ZERO : value;
    }
}
