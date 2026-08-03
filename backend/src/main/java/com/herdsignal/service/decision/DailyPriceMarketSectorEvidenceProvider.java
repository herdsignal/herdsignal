package com.herdsignal.service.decision;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.repository.DailyPriceRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

/** DB의 수정 종가만 읽어 시장·섹터 설명 맥락을 계산한다. */
@Component
@RequiredArgsConstructor
public class DailyPriceMarketSectorEvidenceProvider implements MarketSectorEvidenceProvider {
    private static final int LOOKBACK_CALENDAR_DAYS = 520;
    private final DailyPriceRepository dailyPriceRepository;
    private final MarketSectorContextCalculator calculator;

    @Override
    public Optional<MarketSectorEvidenceSnapshot> contextAsOf(
            String ticker,
            String sectorEtf,
            LocalDate asOfDate
    ) {
        if (ticker == null || ticker.isBlank() || asOfDate == null) return Optional.empty();
        String normalizedTicker = ticker.trim().toUpperCase(Locale.ROOT);
        String normalizedSector = sectorEtf == null || sectorEtf.isBlank()
                ? null : sectorEtf.trim().toUpperCase(Locale.ROOT);
        List<String> requested = new ArrayList<>(List.of(normalizedTicker, "SPY"));
        if (normalizedSector != null) requested.add(normalizedSector);
        List<String> required = requested.stream().distinct().toList();
        List<DailyPrice> rows = dailyPriceRepository.findPricesForTickersBetween(
                required, asOfDate.minusDays(LOOKBACK_CALENDAR_DAYS), asOfDate);
        Map<String, List<MarketSectorPricePoint>> grouped = rows.stream()
                .collect(Collectors.groupingBy(
                        row -> row.getTicker().toUpperCase(Locale.ROOT),
                        Collectors.mapping(this::point, Collectors.toList())));
        MarketSectorEvidenceSnapshot result = calculator.calculate(
                normalizedTicker,
                normalizedSector,
                asOfDate,
                grouped.getOrDefault(normalizedTicker, List.of()),
                grouped.getOrDefault("SPY", List.of()),
                normalizedSector == null ? List.of() : grouped.getOrDefault(normalizedSector, List.of()));
        return Optional.ofNullable(result);
    }

    private MarketSectorPricePoint point(DailyPrice row) {
        OffsetDateTime observedAt = row.getCreatedAt() == null
                ? null : row.getCreatedAt().atOffset(ZoneOffset.UTC);
        return new MarketSectorPricePoint(row.getPriceDate(), row.getClosePrice(), observedAt);
    }
}
