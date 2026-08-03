package com.herdsignal.service.decision;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class MarketSectorContextCalculatorTest {
    private final MarketSectorContextCalculator calculator = new MarketSectorContextCalculator();

    @Test
    void separatesMarketSectorAndStockSpecificPathsWithoutUsingFuturePrices() {
        LocalDate start = LocalDate.of(2025, 1, 2);
        Series series = series(start, 240);
        LocalDate asOf = start.plusDays(220);

        MarketSectorEvidenceSnapshot baseline = calculator.calculate(
                "NVDA", "XLK", asOf,
                series.stock(), series.market(), series.sector());
        MarketSectorEvidenceSnapshot withFutureShock = calculator.calculate(
                "NVDA", "XLK", asOf,
                withFuture(series.stock(), asOf),
                withFuture(series.market(), asOf),
                withFuture(series.sector(), asOf));

        assertThat(baseline).isNotNull();
        assertThat(baseline.hasMarketContext()).isTrue();
        assertThat(baseline.hasSectorContext()).isTrue();
        assertThat(baseline.hasStockAttribution()).isTrue();
        assertThat(baseline.asOfDate()).isEqualTo(asOf);
        assertThat(baseline.downsideAttribution())
                .isIn("MARKET_COMMON", "SECTOR_COMMON", "STOCK_SPECIFIC", "MIXED",
                        "NO_DOWNSIDE_ATTRIBUTION");
        assertThat(withFutureShock).isEqualTo(baseline);
    }

    @Test
    void returnsNoSnapshotWhenMarketHistoryCannotSupportLongTermContext() {
        Series series = series(LocalDate.of(2026, 1, 2), 120);

        MarketSectorEvidenceSnapshot result = calculator.calculate(
                "NVDA", "XLK", LocalDate.of(2026, 6, 1),
                series.stock(), series.market(), series.sector());

        assertThat(result).isNull();
    }

    @Test
    void keepsMarketContextButDoesNotSubstituteSpyWhenSectorHistoryIsMissing() {
        LocalDate start = LocalDate.of(2025, 1, 2);
        Series series = series(start, 240);
        LocalDate asOf = start.plusDays(220);

        MarketSectorEvidenceSnapshot result = calculator.calculate(
                "NVDA", "XLK", asOf,
                series.stock(), series.market(), List.of());

        assertThat(result).isNotNull();
        assertThat(result.hasMarketContext()).isTrue();
        assertThat(result.hasSectorContext()).isFalse();
        assertThat(result.hasStockAttribution()).isFalse();
        assertThat(result.sectorReturn63()).isNull();
        assertThat(result.sectorRelativeReturn63()).isNull();
        assertThat(result.downsideAttribution()).isNull();
    }

    private Series series(LocalDate start, int points) {
        List<MarketSectorPricePoint> stock = new ArrayList<>();
        List<MarketSectorPricePoint> market = new ArrayList<>();
        List<MarketSectorPricePoint> sector = new ArrayList<>();
        double stockPrice = 100.0;
        double marketPrice = 100.0;
        double sectorPrice = 100.0;
        for (int i = 0; i < points; i++) {
            LocalDate date = start.plusDays(i);
            if (i > 0) {
                double marketReturn = 0.0005 + 0.004 * Math.sin(i * 0.31);
                double sectorExcess = 0.0015 * Math.cos(i * 0.19);
                double specific = i >= points - 21 ? -0.001 : 0.0002 * Math.sin(i * 0.43);
                marketPrice *= Math.exp(marketReturn);
                sectorPrice *= Math.exp(marketReturn + sectorExcess);
                stockPrice *= Math.exp(1.15 * marketReturn + 0.75 * sectorExcess + specific);
            }
            OffsetDateTime observedAt = date.atTime(22, 0).atOffset(ZoneOffset.UTC);
            market.add(point(date, marketPrice, observedAt));
            sector.add(point(date, sectorPrice, observedAt));
            stock.add(point(date, stockPrice, observedAt));
        }
        return new Series(stock, market, sector);
    }

    private List<MarketSectorPricePoint> withFuture(
            List<MarketSectorPricePoint> source,
            LocalDate asOf
    ) {
        List<MarketSectorPricePoint> result = new ArrayList<>(source);
        result.add(point(
                asOf.plusDays(1),
                source.get(source.size() - 1).close().doubleValue() * 10.0,
                asOf.plusDays(1).atStartOfDay().atOffset(ZoneOffset.UTC)));
        return result;
    }

    private MarketSectorPricePoint point(
            LocalDate date,
            double close,
            OffsetDateTime observedAt
    ) {
        return new MarketSectorPricePoint(date, BigDecimal.valueOf(close), observedAt);
    }

    private record Series(
            List<MarketSectorPricePoint> stock,
            List<MarketSectorPricePoint> market,
            List<MarketSectorPricePoint> sector
    ) {
    }
}
