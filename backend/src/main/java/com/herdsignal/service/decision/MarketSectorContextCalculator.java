package com.herdsignal.service.decision;

import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 가격의 시장·섹터 공통 부분과 종목 고유 부분을 설명 목적으로만 분리한다.
 * 최근 21수익률의 계수는 그 직전 126수익률에서만 추정해 귀속 구간 누수를 막는다.
 */
@Component
public class MarketSectorContextCalculator {
    static final String SOURCE_VERSION = "MARKET_SECTOR_CONTEXT_V1";
    private static final int MARKET_RETURN_WINDOW = 63;
    private static final int MARKET_TREND_WINDOW = 200;
    private static final int REGRESSION_WINDOW = 126;
    private static final int ATTRIBUTION_WINDOW = 21;
    private static final int SCALE = 8;

    public MarketSectorEvidenceSnapshot calculate(
            String ticker,
            String sectorEtf,
            LocalDate requestedAsOf,
            List<MarketSectorPricePoint> stockPoints,
            List<MarketSectorPricePoint> marketPoints,
            List<MarketSectorPricePoint> sectorPoints
    ) {
        List<MarketSectorPricePoint> market = valid(marketPoints, requestedAsOf);
        if (market.size() < MARKET_TREND_WINDOW) return null;
        LocalDate asOf = market.get(market.size() - 1).date();
        BigDecimal marketReturn = simpleReturn(market, MARKET_RETURN_WINDOW);
        BigDecimal marketDrawdown = drawdown(market, MARKET_RETURN_WINDOW);
        BigDecimal marketVolatility = realizedVolatility(market, MARKET_RETURN_WINDOW);
        BigDecimal marketTrend = trendVsAverage(market, MARKET_TREND_WINDOW);

        List<MarketSectorPricePoint> sector = sameSessionOrEmpty(valid(sectorPoints, asOf), asOf);
        BigDecimal sectorReturn = simpleReturn(sector, MARKET_RETURN_WINDOW);
        BigDecimal sectorRelative = sectorReturn == null || marketReturn == null
                ? null : scaled(sectorReturn.subtract(marketReturn));
        BigDecimal sectorTrend = trendVsAverage(sector, MARKET_TREND_WINDOW);

        List<MarketSectorPricePoint> stock = sameSessionOrEmpty(valid(stockPoints, asOf), asOf);
        Attribution attribution = "SPY".equalsIgnoreCase(ticker)
                ? null : attribution(stock, market, sector);
        OffsetDateTime observedAt = latestObservedAt(stock, market, sector);
        return new MarketSectorEvidenceSnapshot(
                ticker,
                sectorEtf,
                asOf,
                observedAt,
                SOURCE_VERSION,
                marketReturn,
                marketDrawdown,
                marketVolatility,
                marketTrend,
                sectorReturn,
                sectorRelative,
                sectorTrend,
                attribution == null ? null : attribution.stockReturn(),
                attribution == null ? null : attribution.marketContribution(),
                attribution == null ? null : attribution.sectorContribution(),
                attribution == null ? null : attribution.stockSpecificContribution(),
                attribution == null ? null : attribution.classification()
        );
    }

    private Attribution attribution(
            List<MarketSectorPricePoint> stock,
            List<MarketSectorPricePoint> market,
            List<MarketSectorPricePoint> sector
    ) {
        Map<LocalDate, Double> stockClose = closeByDate(stock);
        Map<LocalDate, Double> marketClose = closeByDate(market);
        Map<LocalDate, Double> sectorClose = closeByDate(sector);
        List<LocalDate> dates = stockClose.keySet().stream()
                .filter(marketClose::containsKey)
                .filter(sectorClose::containsKey)
                .sorted()
                .toList();
        int requiredReturns = REGRESSION_WINDOW + ATTRIBUTION_WINDOW;
        if (dates.size() <= requiredReturns) return null;

        List<ReturnRow> returns = new ArrayList<>();
        for (int i = 1; i < dates.size(); i++) {
            LocalDate previous = dates.get(i - 1);
            LocalDate current = dates.get(i);
            double stockReturn = logReturn(stockClose.get(previous), stockClose.get(current));
            double marketReturn = logReturn(marketClose.get(previous), marketClose.get(current));
            double sectorReturn = logReturn(sectorClose.get(previous), sectorClose.get(current));
            if (finite(stockReturn, marketReturn, sectorReturn)) {
                returns.add(new ReturnRow(stockReturn, marketReturn, sectorReturn - marketReturn));
            }
        }
        if (returns.size() < requiredReturns) return null;
        int evaluationStart = returns.size() - ATTRIBUTION_WINDOW;
        List<ReturnRow> fit = returns.subList(
                evaluationStart - REGRESSION_WINDOW, evaluationStart);
        double[] coefficients = ordinaryLeastSquares(fit);
        if (coefficients == null) return null;

        double stockTotal = 0.0;
        double marketContribution = 0.0;
        double sectorContribution = 0.0;
        double stockSpecificContribution = 0.0;
        for (ReturnRow row : returns.subList(evaluationStart, returns.size())) {
            double marketPart = coefficients[1] * row.marketReturn();
            double sectorPart = coefficients[2] * row.sectorExcessReturn();
            double specificPart = row.stockReturn() - marketPart - sectorPart;
            stockTotal += row.stockReturn();
            marketContribution += marketPart;
            sectorContribution += sectorPart;
            stockSpecificContribution += specificPart;
        }
        return new Attribution(
                fromLogReturn(stockTotal),
                fromLogReturn(marketContribution),
                fromLogReturn(sectorContribution),
                fromLogReturn(stockSpecificContribution),
                classify(stockTotal, marketContribution, sectorContribution, stockSpecificContribution)
        );
    }

    private double[] ordinaryLeastSquares(List<ReturnRow> rows) {
        double[][] matrix = new double[3][3];
        double[] vector = new double[3];
        for (ReturnRow row : rows) {
            double[] x = {1.0, row.marketReturn(), row.sectorExcessReturn()};
            for (int i = 0; i < 3; i++) {
                vector[i] += x[i] * row.stockReturn();
                for (int j = 0; j < 3; j++) matrix[i][j] += x[i] * x[j];
            }
        }
        return solve3x3(matrix, vector);
    }

    private double[] solve3x3(double[][] source, double[] values) {
        double[][] matrix = new double[3][4];
        for (int i = 0; i < 3; i++) {
            System.arraycopy(source[i], 0, matrix[i], 0, 3);
            matrix[i][3] = values[i];
        }
        for (int column = 0; column < 3; column++) {
            int pivot = column;
            for (int row = column + 1; row < 3; row++) {
                if (Math.abs(matrix[row][column]) > Math.abs(matrix[pivot][column])) pivot = row;
            }
            if (Math.abs(matrix[pivot][column]) < 1e-12) return null;
            double[] temporary = matrix[column];
            matrix[column] = matrix[pivot];
            matrix[pivot] = temporary;
            double divisor = matrix[column][column];
            for (int j = column; j < 4; j++) matrix[column][j] /= divisor;
            for (int row = 0; row < 3; row++) {
                if (row == column) continue;
                double factor = matrix[row][column];
                for (int j = column; j < 4; j++) matrix[row][j] -= factor * matrix[column][j];
            }
        }
        return new double[]{matrix[0][3], matrix[1][3], matrix[2][3]};
    }

    private String classify(
            double stockReturn,
            double marketContribution,
            double sectorContribution,
            double stockSpecificContribution
    ) {
        if (stockReturn >= 0.0) return "NO_DOWNSIDE_ATTRIBUTION";
        double minimum = Math.min(marketContribution, Math.min(sectorContribution, stockSpecificContribution));
        if (minimum >= 0.0) return "MIXED";
        if (minimum == marketContribution) return "MARKET_COMMON";
        if (minimum == sectorContribution) return "SECTOR_COMMON";
        return "STOCK_SPECIFIC";
    }

    private List<MarketSectorPricePoint> valid(
            List<MarketSectorPricePoint> points,
            LocalDate asOf
    ) {
        if (points == null || asOf == null) return List.of();
        return points.stream()
                .filter(point -> point != null && point.date() != null && point.close() != null)
                .filter(point -> !point.date().isAfter(asOf))
                .filter(point -> point.close().signum() > 0)
                .sorted(Comparator.comparing(MarketSectorPricePoint::date))
                .toList();
    }

    private Map<LocalDate, Double> closeByDate(List<MarketSectorPricePoint> points) {
        Map<LocalDate, Double> values = new HashMap<>();
        points.forEach(point -> values.put(point.date(), point.close().doubleValue()));
        return values;
    }

    private BigDecimal simpleReturn(List<MarketSectorPricePoint> points, int periods) {
        if (points.size() <= periods) return null;
        double start = points.get(points.size() - periods - 1).close().doubleValue();
        double end = points.get(points.size() - 1).close().doubleValue();
        return finite(start, end) && start > 0.0 ? decimal(end / start - 1.0) : null;
    }

    private BigDecimal drawdown(List<MarketSectorPricePoint> points, int periods) {
        if (points.size() < periods) return null;
        List<MarketSectorPricePoint> window = points.subList(points.size() - periods, points.size());
        double maximum = window.stream().mapToDouble(point -> point.close().doubleValue()).max().orElse(0.0);
        double latest = window.get(window.size() - 1).close().doubleValue();
        return maximum > 0.0 ? decimal(latest / maximum - 1.0) : null;
    }

    private BigDecimal realizedVolatility(List<MarketSectorPricePoint> points, int periods) {
        if (points.size() <= periods) return null;
        List<Double> returns = new ArrayList<>();
        for (int i = points.size() - periods; i < points.size(); i++) {
            returns.add(logReturn(
                    points.get(i - 1).close().doubleValue(), points.get(i).close().doubleValue()));
        }
        double mean = returns.stream().mapToDouble(Double::doubleValue).average().orElse(0.0);
        double variance = returns.stream()
                .mapToDouble(value -> Math.pow(value - mean, 2))
                .sum() / Math.max(1, returns.size() - 1);
        return decimal(Math.sqrt(variance * 252.0));
    }

    private BigDecimal trendVsAverage(List<MarketSectorPricePoint> points, int periods) {
        if (points.size() < periods) return null;
        List<MarketSectorPricePoint> window = points.subList(points.size() - periods, points.size());
        double average = window.stream().mapToDouble(point -> point.close().doubleValue()).average().orElse(0.0);
        double latest = window.get(window.size() - 1).close().doubleValue();
        return average > 0.0 ? decimal(latest / average - 1.0) : null;
    }

    private List<MarketSectorPricePoint> sameSessionOrEmpty(
            List<MarketSectorPricePoint> points,
            LocalDate expectedDate
    ) {
        if (points.isEmpty() || !points.get(points.size() - 1).date().equals(expectedDate)) {
            return List.of();
        }
        return points;
    }

    @SafeVarargs
    private final OffsetDateTime latestObservedAt(List<MarketSectorPricePoint>... series) {
        return java.util.Arrays.stream(series)
                .flatMap(List::stream)
                .map(MarketSectorPricePoint::observedAt)
                .filter(value -> value != null)
                .max(Comparator.naturalOrder())
                .orElse(null);
    }

    private double logReturn(double start, double end) {
        return start > 0.0 && end > 0.0 ? Math.log(end / start) : Double.NaN;
    }

    private boolean finite(double... values) {
        for (double value : values) if (!Double.isFinite(value)) return false;
        return true;
    }

    private BigDecimal fromLogReturn(double value) {
        return decimal(Math.expm1(value));
    }

    private BigDecimal decimal(double value) {
        return Double.isFinite(value)
                ? BigDecimal.valueOf(value).setScale(SCALE, RoundingMode.HALF_UP)
                : null;
    }

    private BigDecimal scaled(BigDecimal value) {
        return value.setScale(SCALE, RoundingMode.HALF_UP);
    }

    private record ReturnRow(
            double stockReturn,
            double marketReturn,
            double sectorExcessReturn
    ) {
    }

    private record Attribution(
            BigDecimal stockReturn,
            BigDecimal marketContribution,
            BigDecimal sectorContribution,
            BigDecimal stockSpecificContribution,
            String classification
    ) {
    }
}
