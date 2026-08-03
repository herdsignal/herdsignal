package com.herdsignal.service;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.domain.SignalJournal;
import com.herdsignal.dto.JournalHorizonOutcomeResponse;
import com.herdsignal.repository.DailyPriceRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

@Service
public class SignalJournalOutcomeService {

    private static final int PRICE_LOOKUP_DAYS = 7;
    private static final List<Horizon> HORIZONS = List.of(
            new Horizon("1M", 1),
            new Horizon("3M", 3),
            new Horizon("6M", 6)
    );

    private final DailyPriceRepository dailyPriceRepository;
    private final PricePathAttributionService pricePathAttributionService;

    @Autowired
    public SignalJournalOutcomeService(
            DailyPriceRepository dailyPriceRepository,
            PricePathAttributionService pricePathAttributionService
    ) {
        this.dailyPriceRepository = dailyPriceRepository;
        this.pricePathAttributionService = pricePathAttributionService;
    }

    SignalJournalOutcomeService(DailyPriceRepository dailyPriceRepository) {
        this(dailyPriceRepository, new PricePathAttributionService(dailyPriceRepository));
    }

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

        List<JournalHorizonOutcomeResponse> outcomes = pricePathAttributionService.evaluate(
                        journal.getTicker(), reference.getPriceDate(), reference.getClosePrice(),
                        HORIZONS.stream().map(Horizon::months).toList(), latestMarketDate).stream()
                .map(this::outcome)
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

    private JournalHorizonOutcomeResponse outcome(PricePathAttributionService.Outcome row) {
        return JournalHorizonOutcomeResponse.builder()
                .horizon(HORIZONS.stream()
                        .filter(item -> item.months() == row.horizonMonths())
                        .map(Horizon::label).findFirst().orElse(row.horizonMonths() + "M"))
                .targetDate(row.targetDate())
                .status(row.status())
                .priceDate(row.priceDate())
                .closePrice(row.closePrice())
                .returnPct(row.returnPct())
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
