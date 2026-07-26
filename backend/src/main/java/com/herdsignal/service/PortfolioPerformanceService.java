package com.herdsignal.service;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.domain.PortfolioLedgerEntry;
import com.herdsignal.dto.PortfolioPerformancePointResponse;
import com.herdsignal.dto.PortfolioPerformanceResponse;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.PortfolioLedgerEntryRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class PortfolioPerformanceService {

    private static final String BENCHMARK = "SPY";

    private final PortfolioLedgerEntryRepository ledgerRepository;
    private final DailyPriceRepository priceRepository;

    @Transactional(readOnly = true)
    public PortfolioPerformanceResponse getPerformance(String userId) {
        List<PortfolioLedgerEntry> entries =
                ledgerRepository.findByUserIdOrderByOccurredOnAscIdAsc(userId);
        if (entries.isEmpty()) return unavailable("EMPTY_LEDGER", "거래 원장이 비어 있습니다.");

        var ledgerCheck = new PortfolioLedgerCalculator().calculate(entries);
        if (!ledgerCheck.errors().isEmpty()) {
            return PortfolioPerformanceResponse.builder()
                    .status("INVALID_PERFORMANCE_INPUT")
                    .method("DAILY_TWR_END_OF_DAY_FLOW")
                    .benchmark(BENCHMARK)
                    .points(List.of())
                    .warnings(List.of())
                    .errors(ledgerCheck.errors())
                    .build();
        }
        boolean hasDeposit = entries.stream()
                .anyMatch(entry -> entry.getEntryType().name().equals("DEPOSIT"));
        if (!hasDeposit) {
            return unavailable(
                    "MISSING_OPENING_CAPITAL",
                    "입금 기록이 없어 외부 자본과 투자 성과를 분리할 수 없습니다."
            );
        }

        LocalDate start = entries.get(0).getOccurredOn();
        LocalDate end = priceRepository.findLatestPriceDate().orElse(null);
        if (end == null || end.isBefore(start)) {
            return unavailable("INSUFFICIENT_HISTORY", "원장 기간의 가격 데이터가 없습니다.");
        }
        List<String> tickers = new ArrayList<>(entries.stream()
                .map(PortfolioLedgerEntry::getTicker)
                .filter(java.util.Objects::nonNull)
                .distinct()
                .toList());
        if (!tickers.contains(BENCHMARK)) tickers.add(BENCHMARK);

        Map<LocalDate, Map<String, BigDecimal>> closes = new LinkedHashMap<>();
        for (DailyPrice price : priceRepository.findPricesForTickersBetween(tickers, start, end)) {
            closes.computeIfAbsent(price.getPriceDate(), ignored -> new LinkedHashMap<>())
                    .put(price.getTicker(), price.getClosePrice());
        }
        closes.entrySet().removeIf(entry -> !entry.getValue().containsKey(BENCHMARK));
        var result = new PortfolioTwrCalculator().calculate(entries, closes, BENCHMARK);
        BigDecimal excess = result.portfolioReturnPct() == null
                ? null
                : result.portfolioReturnPct().subtract(result.benchmarkReturnPct());
        return PortfolioPerformanceResponse.builder()
                .status(result.status())
                .method("DAILY_TWR_END_OF_DAY_FLOW")
                .benchmark(BENCHMARK)
                .startDate(result.points().isEmpty() ? null : result.points().get(0).date())
                .endDate(result.points().isEmpty()
                        ? null
                        : result.points().get(result.points().size() - 1).date())
                .portfolioReturnPct(result.portfolioReturnPct())
                .benchmarkReturnPct(result.benchmarkReturnPct())
                .excessReturnPct(excess)
                .points(result.points().stream()
                        .map(point -> PortfolioPerformancePointResponse.builder()
                                .date(point.date())
                                .portfolioIndex(point.portfolioIndex())
                                .benchmarkIndex(point.benchmarkIndex())
                                .build())
                        .toList())
                .warnings(List.of("날짜만 기록하므로 입출금은 해당 거래일 종가 시점으로 처리합니다."))
                .errors(result.errors())
                .build();
    }

    private PortfolioPerformanceResponse unavailable(String status, String error) {
        return PortfolioPerformanceResponse.builder()
                .status(status)
                .method("DAILY_TWR_END_OF_DAY_FLOW")
                .benchmark(BENCHMARK)
                .points(List.of())
                .warnings(List.of())
                .errors(List.of(error))
                .build();
    }
}
