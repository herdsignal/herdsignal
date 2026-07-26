package com.herdsignal.service;

import com.herdsignal.domain.PortfolioLedgerEntry;
import com.herdsignal.domain.PortfolioLedgerEntryType;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 날짜만 있는 거래 원장을 거래일 종가 기준으로 재생한다.
 * 외부 현금흐름은 당일 말 발생으로 간주하고 일별 TWR에서 제거한다.
 */
final class PortfolioTwrCalculator {

    private static final BigDecimal ZERO = BigDecimal.ZERO;
    private static final BigDecimal ONE = BigDecimal.ONE;
    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);
    private static final MathContext MC = new MathContext(16, RoundingMode.HALF_UP);

    Result calculate(
            List<PortfolioLedgerEntry> entries,
            Map<LocalDate, Map<String, BigDecimal>> closes,
            String benchmarkTicker
    ) {
        Map<String, BigDecimal> quantities = new HashMap<>();
        BigDecimal cash = ZERO;
        BigDecimal portfolioGrowth = ONE;
        BigDecimal benchmarkGrowth = ONE;
        BigDecimal benchmarkShares = ZERO;
        BigDecimal previousValue = null;
        BigDecimal previousBenchmarkValue = null;
        int eventIndex = 0;
        List<Point> points = new ArrayList<>();
        List<String> errors = new ArrayList<>();

        for (var day : closes.entrySet()) {
            LocalDate date = day.getKey();
            Map<String, BigDecimal> dayCloses = day.getValue();
            BigDecimal externalFlow = ZERO;

            while (eventIndex < entries.size()
                    && !entries.get(eventIndex).getOccurredOn().isAfter(date)) {
                PortfolioLedgerEntry entry = entries.get(eventIndex++);
                BigDecimal gross = entry.getGrossAmount();
                BigDecimal fee = entry.getFeeAmount();
                switch (entry.getEntryType()) {
                    case DEPOSIT -> {
                        cash = cash.add(gross);
                        externalFlow = externalFlow.add(gross);
                    }
                    case WITHDRAWAL -> {
                        cash = cash.subtract(gross);
                        externalFlow = externalFlow.subtract(gross);
                    }
                    case DIVIDEND -> cash = cash.add(gross);
                    case FEE -> cash = cash.subtract(gross);
                    case BUY -> {
                        quantities.merge(entry.getTicker(), entry.getQuantity(), BigDecimal::add);
                        cash = cash.subtract(gross.add(fee));
                    }
                    case SELL -> {
                        BigDecimal remaining = quantities.getOrDefault(entry.getTicker(), ZERO)
                                .subtract(entry.getQuantity());
                        if (remaining.compareTo(ZERO) < 0) {
                            errors.add(entry.getTicker() + " 초과매도로 성과를 계산할 수 없습니다.");
                            return invalid(errors);
                        }
                        quantities.put(entry.getTicker(), remaining);
                        cash = cash.add(gross.subtract(fee));
                    }
                    case SPLIT -> quantities.computeIfPresent(
                            entry.getTicker(),
                            (ticker, quantity) -> quantity.multiply(entry.getSplitRatio())
                    );
                }
            }

            BigDecimal value = cash;
            for (var holding : quantities.entrySet()) {
                if (holding.getValue().compareTo(ZERO) == 0) continue;
                BigDecimal close = dayCloses.get(holding.getKey());
                if (close == null) {
                    errors.add(date + " " + holding.getKey() + " 종가가 누락됐습니다.");
                    return invalid(errors);
                }
                value = value.add(holding.getValue().multiply(close, MC));
            }

            BigDecimal benchmarkClose = dayCloses.get(benchmarkTicker);
            if (benchmarkClose == null) continue;
            BigDecimal benchmarkBeforeFlow = benchmarkShares.multiply(benchmarkClose, MC);
            BigDecimal benchmarkValue = benchmarkBeforeFlow.add(externalFlow);
            if (externalFlow.compareTo(ZERO) != 0) {
                benchmarkShares = benchmarkShares.add(
                        externalFlow.divide(benchmarkClose, 12, RoundingMode.HALF_UP)
                );
                if (benchmarkShares.compareTo(ZERO) < 0) {
                    errors.add("SPY 가상 계좌보다 큰 출금이 있어 벤치마크를 계산할 수 없습니다.");
                    return invalid(errors);
                }
            }

            if (previousValue == null) {
                if (value.compareTo(ZERO) <= 0 || benchmarkValue.compareTo(ZERO) <= 0) continue;
                previousValue = value;
                previousBenchmarkValue = benchmarkValue;
                points.add(new Point(date, HUNDRED, HUNDRED));
                continue;
            }

            if (previousValue.compareTo(ZERO) <= 0 || previousBenchmarkValue.compareTo(ZERO) <= 0) {
                errors.add("성과 연결 구간의 계좌 가치가 0 이하입니다.");
                return invalid(errors);
            }
            BigDecimal dailyReturn = value.subtract(externalFlow)
                    .divide(previousValue, 12, RoundingMode.HALF_UP)
                    .subtract(ONE);
            BigDecimal benchmarkReturn = benchmarkBeforeFlow
                    .divide(previousBenchmarkValue, 12, RoundingMode.HALF_UP)
                    .subtract(ONE);
            portfolioGrowth = portfolioGrowth.multiply(ONE.add(dailyReturn), MC);
            benchmarkGrowth = benchmarkGrowth.multiply(ONE.add(benchmarkReturn), MC);
            previousValue = value;
            previousBenchmarkValue = benchmarkValue;
            points.add(new Point(
                    date,
                    portfolioGrowth.multiply(HUNDRED).setScale(4, RoundingMode.HALF_UP),
                    benchmarkGrowth.multiply(HUNDRED).setScale(4, RoundingMode.HALF_UP)
            ));
        }

        if (points.size() < 2) {
            return new Result("INSUFFICIENT_HISTORY", null, null, List.of(), List.of(
                    "입금 이후 최소 2개 거래일의 완전한 가격이 필요합니다."
            ));
        }
        return new Result(
                "PERFORMANCE_READY",
                portfolioGrowth.subtract(ONE).multiply(HUNDRED)
                        .setScale(4, RoundingMode.HALF_UP),
                benchmarkGrowth.subtract(ONE).multiply(HUNDRED)
                        .setScale(4, RoundingMode.HALF_UP),
                List.copyOf(points),
                List.of()
        );
    }

    private Result invalid(List<String> errors) {
        return new Result("INVALID_PERFORMANCE_INPUT", null, null, List.of(), List.copyOf(errors));
    }

    record Result(
            String status,
            BigDecimal portfolioReturnPct,
            BigDecimal benchmarkReturnPct,
            List<Point> points,
            List<String> errors
    ) {}

    record Point(LocalDate date, BigDecimal portfolioIndex, BigDecimal benchmarkIndex) {}
}
