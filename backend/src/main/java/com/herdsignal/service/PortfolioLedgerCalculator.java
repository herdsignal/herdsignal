package com.herdsignal.service;

import com.herdsignal.domain.PortfolioLedgerEntry;
import com.herdsignal.domain.PortfolioLedgerEntryType;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 날짜·ID 순으로 정렬된 불변 거래 원장을 FIFO lot으로 재생한다.
 * 시세 조회와 HTTP 표현은 담당하지 않아 계산 규칙을 독립적으로 검증할 수 있다.
 */
final class PortfolioLedgerCalculator {

    private static final BigDecimal ZERO = BigDecimal.ZERO;
    private static final int CALCULATION_SCALE = 12;

    Calculation calculate(List<PortfolioLedgerEntry> entries) {
        BigDecimal cash = ZERO;
        BigDecimal dividends = ZERO;
        BigDecimal fees = ZERO;
        BigDecimal deposits = ZERO;
        BigDecimal withdrawals = ZERO;
        Map<String, PositionState> states = new LinkedHashMap<>();
        List<String> errors = new ArrayList<>();

        for (PortfolioLedgerEntry entry : entries) {
            BigDecimal gross = entry.getGrossAmount();
            BigDecimal fee = entry.getFeeAmount();
            switch (entry.getEntryType()) {
                case DEPOSIT -> {
                    cash = cash.add(gross);
                    deposits = deposits.add(gross);
                }
                case WITHDRAWAL -> {
                    cash = cash.subtract(gross);
                    withdrawals = withdrawals.add(gross);
                }
                case DIVIDEND -> {
                    cash = cash.add(gross);
                    dividends = dividends.add(gross);
                }
                case FEE -> {
                    cash = cash.subtract(gross);
                    fees = fees.add(gross);
                }
                case BUY -> {
                    cash = cash.subtract(gross.add(fee));
                    fees = fees.add(fee);
                    PositionState state = states.computeIfAbsent(
                            entry.getTicker(),
                            ignored -> new PositionState()
                    );
                    state.lots.addLast(new Lot(entry.getQuantity(), gross.add(fee)));
                }
                case SELL -> {
                    cash = cash.add(gross.subtract(fee));
                    fees = fees.add(fee);
                    PositionState state = states.computeIfAbsent(
                            entry.getTicker(),
                            ignored -> new PositionState()
                    );
                    BigDecimal consumedCost = consume(
                            state,
                            entry.getQuantity(),
                            entry.getTicker(),
                            entry.getId(),
                            errors
                    );
                    if (consumedCost != null) {
                        state.realizedPnl = state.realizedPnl
                                .add(gross.subtract(fee))
                                .subtract(consumedCost);
                    }
                }
                case SPLIT -> {
                    PositionState state = states.computeIfAbsent(
                            entry.getTicker(),
                            ignored -> new PositionState()
                    );
                    ArrayDeque<Lot> adjusted = new ArrayDeque<>();
                    state.lots.forEach(lot -> adjusted.addLast(new Lot(
                            lot.quantity().multiply(entry.getSplitRatio()),
                            lot.cost()
                    )));
                    state.lots.clear();
                    state.lots.addAll(adjusted);
                }
            }
        }

        List<OpenPosition> positions = states.entrySet().stream()
                .map(entry -> openPosition(entry.getKey(), entry.getValue()))
                .filter(position -> position.quantity().compareTo(ZERO) > 0)
                .toList();
        BigDecimal realized = states.values().stream()
                .map(state -> state.realizedPnl)
                .reduce(ZERO, BigDecimal::add);

        return new Calculation(
                cash,
                dividends,
                fees,
                deposits.subtract(withdrawals),
                realized,
                positions,
                List.copyOf(errors)
        );
    }

    private BigDecimal consume(
            PositionState state,
            BigDecimal requested,
            String ticker,
            Long eventId,
            List<String> errors
    ) {
        BigDecimal available = state.lots.stream()
                .map(Lot::quantity)
                .reduce(ZERO, BigDecimal::add);
        if (available.compareTo(requested) < 0) {
            errors.add("%s 매도 수량이 보유 lot을 초과합니다. (원장 #%s)"
                    .formatted(ticker, eventId == null ? "미저장" : eventId));
            return null;
        }

        BigDecimal remaining = requested;
        BigDecimal consumedCost = ZERO;
        while (remaining.compareTo(ZERO) > 0) {
            Lot lot = state.lots.removeFirst();
            BigDecimal used = lot.quantity().min(remaining);
            BigDecimal usedCost = lot.cost()
                    .multiply(used)
                    .divide(lot.quantity(), CALCULATION_SCALE, RoundingMode.HALF_UP);
            consumedCost = consumedCost.add(usedCost);
            remaining = remaining.subtract(used);

            BigDecimal leftover = lot.quantity().subtract(used);
            if (leftover.compareTo(ZERO) > 0) {
                state.lots.addFirst(new Lot(leftover, lot.cost().subtract(usedCost)));
            }
        }
        return consumedCost;
    }

    private OpenPosition openPosition(String ticker, PositionState state) {
        BigDecimal quantity = state.lots.stream()
                .map(Lot::quantity)
                .reduce(ZERO, BigDecimal::add);
        BigDecimal cost = state.lots.stream()
                .map(Lot::cost)
                .reduce(ZERO, BigDecimal::add);
        return new OpenPosition(ticker, quantity, cost, state.realizedPnl);
    }

    record Calculation(
            BigDecimal cashBalance,
            BigDecimal dividends,
            BigDecimal fees,
            BigDecimal netContributions,
            BigDecimal realizedPnl,
            List<OpenPosition> positions,
            List<String> errors
    ) {}

    record OpenPosition(
            String ticker,
            BigDecimal quantity,
            BigDecimal costBasis,
            BigDecimal realizedPnl
    ) {}

    private record Lot(BigDecimal quantity, BigDecimal cost) {}

    private static final class PositionState {
        private final ArrayDeque<Lot> lots = new ArrayDeque<>();
        private BigDecimal realizedPnl = ZERO;
    }
}
