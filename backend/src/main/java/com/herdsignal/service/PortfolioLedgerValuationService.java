package com.herdsignal.service;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.domain.PortfolioLedgerEntry;
import com.herdsignal.dto.PortfolioLedgerPositionResponse;
import com.herdsignal.dto.PortfolioLedgerSummaryResponse;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.PortfolioLedgerEntryRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class PortfolioLedgerValuationService {

    private static final BigDecimal ZERO = BigDecimal.ZERO.setScale(2);

    private final PortfolioLedgerEntryRepository ledgerRepository;
    private final DailyPriceRepository priceRepository;

    @Transactional(readOnly = true)
    public PortfolioLedgerSummaryResponse getSummary(String userId) {
        List<PortfolioLedgerEntry> entries =
                ledgerRepository.findByUserIdOrderByOccurredOnAscIdAsc(userId);
        if (entries.isEmpty()) return emptySummary();

        PortfolioLedgerCalculator.Calculation calculation =
                new PortfolioLedgerCalculator().calculate(entries);
        if (!calculation.errors().isEmpty()) {
            return invalidSummary(calculation);
        }

        List<String> tickers = calculation.positions().stream()
                .map(PortfolioLedgerCalculator.OpenPosition::ticker)
                .toList();
        Map<String, DailyPrice> prices = tickers.isEmpty()
                ? Map.of()
                : priceRepository.findLatestByTickers(tickers).stream()
                        .collect(Collectors.toMap(
                                DailyPrice::getTicker,
                                Function.identity(),
                                (left, right) -> left.getPriceDate().isAfter(right.getPriceDate())
                                        ? left
                                        : right
                        ));

        List<String> warnings = new ArrayList<>();
        if (calculation.cashBalance().compareTo(BigDecimal.ZERO) < 0) {
            warnings.add("현금 잔액이 음수입니다. 누락된 입금 또는 거래를 확인해주세요.");
        }

        List<PortfolioLedgerPositionResponse> positions = calculation.positions().stream()
                .map(position -> value(position, prices.get(position.ticker()), warnings))
                .sorted(Comparator.comparing(PortfolioLedgerPositionResponse::getMarketValue,
                        Comparator.nullsLast(Comparator.reverseOrder())))
                .toList();
        boolean pricingComplete = positions.stream()
                .allMatch(PortfolioLedgerPositionResponse::isPriceAvailable);
        BigDecimal marketValue = pricingComplete
                ? sum(positions, PortfolioLedgerPositionResponse::getMarketValue)
                : null;
        BigDecimal unrealized = pricingComplete
                ? sum(positions, PortfolioLedgerPositionResponse::getUnrealizedPnl)
                : null;
        BigDecimal costBasis = calculation.positions().stream()
                .map(PortfolioLedgerCalculator.OpenPosition::costBasis)
                .reduce(BigDecimal.ZERO, BigDecimal::add);
        LocalDate priceAsOf = positions.stream()
                .map(PortfolioLedgerPositionResponse::getPriceDate)
                .filter(java.util.Objects::nonNull)
                .min(LocalDate::compareTo)
                .orElse(null);

        return PortfolioLedgerSummaryResponse.builder()
                .status(pricingComplete ? "LEDGER_READY" : "PRICE_INCOMPLETE")
                .currency("USD")
                .priceAsOf(priceAsOf)
                .pricingComplete(pricingComplete)
                .cashBalance(money(calculation.cashBalance()))
                .marketValue(moneyOrNull(marketValue))
                .accountValue(pricingComplete
                        ? money(calculation.cashBalance().add(marketValue))
                        : null)
                .costBasis(money(costBasis))
                .realizedPnl(money(calculation.realizedPnl()))
                .unrealizedPnl(moneyOrNull(unrealized))
                .dividends(money(calculation.dividends()))
                .fees(money(calculation.fees()))
                .netContributions(money(calculation.netContributions()))
                .positions(positions)
                .warnings(List.copyOf(warnings))
                .errors(List.of())
                .build();
    }

    private PortfolioLedgerPositionResponse value(
            PortfolioLedgerCalculator.OpenPosition position,
            DailyPrice price,
            List<String> warnings
    ) {
        BigDecimal averageCost = position.costBasis()
                .divide(position.quantity(), 6, RoundingMode.HALF_UP);
        if (price == null || price.getClosePrice() == null) {
            warnings.add(position.ticker() + " 최신 종가가 없어 원장 평가를 완료하지 못했습니다.");
            return PortfolioLedgerPositionResponse.builder()
                    .ticker(position.ticker())
                    .quantity(position.quantity())
                    .averageCost(averageCost)
                    .costBasis(money(position.costBasis()))
                    .realizedPnl(money(position.realizedPnl()))
                    .priceAvailable(false)
                    .build();
        }

        BigDecimal marketValue = position.quantity().multiply(price.getClosePrice());
        BigDecimal unrealized = marketValue.subtract(position.costBasis());
        BigDecimal returnPct = position.costBasis().compareTo(BigDecimal.ZERO) == 0
                ? null
                : unrealized.multiply(BigDecimal.valueOf(100))
                        .divide(position.costBasis(), 4, RoundingMode.HALF_UP);
        return PortfolioLedgerPositionResponse.builder()
                .ticker(position.ticker())
                .quantity(position.quantity())
                .averageCost(averageCost)
                .costBasis(money(position.costBasis()))
                .latestPrice(price.getClosePrice())
                .priceDate(price.getPriceDate())
                .marketValue(money(marketValue))
                .realizedPnl(money(position.realizedPnl()))
                .unrealizedPnl(money(unrealized))
                .unrealizedReturnPct(returnPct)
                .priceAvailable(true)
                .build();
    }

    private PortfolioLedgerSummaryResponse emptySummary() {
        return PortfolioLedgerSummaryResponse.builder()
                .status("EMPTY_LEDGER")
                .currency("USD")
                .pricingComplete(false)
                .cashBalance(ZERO)
                .positions(List.of())
                .warnings(List.of())
                .errors(List.of())
                .build();
    }

    private PortfolioLedgerSummaryResponse invalidSummary(
            PortfolioLedgerCalculator.Calculation calculation
    ) {
        return PortfolioLedgerSummaryResponse.builder()
                .status("INVALID_LEDGER")
                .currency("USD")
                .pricingComplete(false)
                .cashBalance(money(calculation.cashBalance()))
                .positions(List.of())
                .warnings(List.of())
                .errors(calculation.errors())
                .build();
    }

    private BigDecimal sum(
            List<PortfolioLedgerPositionResponse> positions,
            Function<PortfolioLedgerPositionResponse, BigDecimal> mapper
    ) {
        return positions.stream().map(mapper).reduce(BigDecimal.ZERO, BigDecimal::add);
    }

    private BigDecimal money(BigDecimal value) {
        return value.setScale(2, RoundingMode.HALF_UP);
    }

    private BigDecimal moneyOrNull(BigDecimal value) {
        return value == null ? null : money(value);
    }
}
