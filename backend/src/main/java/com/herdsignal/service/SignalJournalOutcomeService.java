package com.herdsignal.service;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.domain.SignalJournal;
import com.herdsignal.dto.JournalHorizonOutcomeResponse;
import com.herdsignal.repository.DailyPriceRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.List;

@Service
@RequiredArgsConstructor
public class SignalJournalOutcomeService {

    private static final int PRICE_LOOKUP_DAYS = 7;
    private static final List<Horizon> HORIZONS = List.of(
            new Horizon("1M", 1),
            new Horizon("3M", 3),
            new Horizon("6M", 6)
    );

    private final DailyPriceRepository dailyPriceRepository;

    public Result evaluate(SignalJournal journal, LocalDate latestMarketDate) {
        LocalDate observationDate = observationDate(journal);
        DailyPrice reference = referencePrice(journal.getTicker(), observationDate);
        if (
                reference == null
                || reference.getClosePrice() == null
                || reference.getClosePrice().compareTo(BigDecimal.ZERO) <= 0
        ) {
            return new Result(
                    observationDate,
                    null,
                    null,
                    unavailableOutcomes(observationDate)
            );
        }

        List<JournalHorizonOutcomeResponse> outcomes = HORIZONS.stream()
                .map(horizon -> evaluateHorizon(
                        journal.getTicker(),
                        reference,
                        horizon,
                        latestMarketDate
                ))
                .toList();
        return new Result(
                observationDate,
                reference.getPriceDate(),
                reference.getClosePrice(),
                outcomes
        );
    }

    private DailyPrice referencePrice(String ticker, LocalDate observationDate) {
        if (ticker == null || ticker.isBlank() || observationDate == null) return null;
        return dailyPriceRepository
                .findTopByTickerAndPriceDateBetweenAndClosePriceIsNotNullOrderByPriceDateDesc(
                        ticker,
                        observationDate.minusDays(PRICE_LOOKUP_DAYS),
                        observationDate
                )
                .orElse(null);
    }

    private JournalHorizonOutcomeResponse evaluateHorizon(
            String ticker,
            DailyPrice reference,
            Horizon horizon,
            LocalDate latestMarketDate
    ) {
        LocalDate targetDate = reference.getPriceDate().plusMonths(horizon.months());
        if (latestMarketDate == null || targetDate.isAfter(latestMarketDate)) {
            return outcome(horizon.label(), targetDate, "PENDING", null, null);
        }

        DailyPrice target = dailyPriceRepository
                .findTopByTickerAndPriceDateBetweenAndClosePriceIsNotNullOrderByPriceDateAsc(
                        ticker,
                        targetDate,
                        targetDate.plusDays(PRICE_LOOKUP_DAYS)
                )
                .orElse(null);
        if (target == null) {
            return outcome(horizon.label(), targetDate, "UNAVAILABLE", null, null);
        }

        BigDecimal returnPct = target.getClosePrice()
                .subtract(reference.getClosePrice())
                .divide(reference.getClosePrice(), 8, RoundingMode.HALF_UP)
                .multiply(BigDecimal.valueOf(100))
                .setScale(4, RoundingMode.HALF_UP);
        return outcome(horizon.label(), targetDate, "AVAILABLE", target, returnPct);
    }

    private List<JournalHorizonOutcomeResponse> unavailableOutcomes(LocalDate observationDate) {
        return HORIZONS.stream()
                .map(horizon -> JournalHorizonOutcomeResponse.builder()
                        .horizon(horizon.label())
                        .targetDate(observationDate == null
                                ? null
                                : observationDate.plusMonths(horizon.months()))
                        .status("UNAVAILABLE")
                        .build())
                .toList();
    }

    private JournalHorizonOutcomeResponse outcome(
            String label,
            LocalDate targetDate,
            String status,
            DailyPrice price,
            BigDecimal returnPct
    ) {
        return JournalHorizonOutcomeResponse.builder()
                .horizon(label)
                .targetDate(targetDate)
                .status(status)
                .priceDate(price == null ? null : price.getPriceDate())
                .closePrice(price == null ? null : price.getClosePrice())
                .returnPct(returnPct)
                .build();
    }

    private LocalDate observationDate(SignalJournal journal) {
        if (journal.getScoreDate() != null) return journal.getScoreDate();
        if (journal.getRecordedAt() != null) return journal.getRecordedAt().toLocalDate();
        return journal.getCreatedAt() == null ? null : journal.getCreatedAt().toLocalDate();
    }

    private record Horizon(String label, int months) {
    }

    public record Result(
            LocalDate observationDate,
            LocalDate referencePriceDate,
            BigDecimal referencePrice,
            List<JournalHorizonOutcomeResponse> outcomes
    ) {
    }
}
