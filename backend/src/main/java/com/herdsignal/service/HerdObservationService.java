package com.herdsignal.service;

import com.herdsignal.domain.HerdObservation;
import com.herdsignal.domain.Stock;
import com.herdsignal.dto.HerdObservationBatchResponse;
import com.herdsignal.dto.HerdObservationHistoryPoint;
import com.herdsignal.dto.HerdObservationHistoryResponse;
import com.herdsignal.dto.HerdObservationResponse;
import com.herdsignal.repository.HerdObservationRepository;
import com.herdsignal.repository.StockRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
public class HerdObservationService {
    static final String STATE_MODEL_VERSION = "HERD_STATE_S1";
    static final String DAILY_MODEL_VERSION = "HERD_DAILY_D1";
    static final int DEFAULT_HISTORY_LIMIT = 52;
    static final int MAX_HISTORY_LIMIT = 260;
    static final int MAX_BATCH_SIZE = 100;
    private static final int STALE_AFTER_BUSINESS_SESSIONS = 2;
    private static final String TICKER_PATTERN = "^[A-Z][A-Z0-9.-]{0,9}$";
    private final HerdObservationRepository repository;
    private final StockRepository stockRepository;
    private final UsMarketSessionClock marketSessionClock;
    private final UserActionBoundary actionBoundary;

    @Autowired
    public HerdObservationService(
            HerdObservationRepository repository,
            StockRepository stockRepository,
            UsMarketSessionClock marketSessionClock,
            UserActionBoundary actionBoundary
    ) {
        this.repository = repository;
        this.stockRepository = stockRepository;
        this.marketSessionClock = marketSessionClock;
        this.actionBoundary = actionBoundary;
    }

    @Transactional(readOnly = true)
    public HerdObservationResponse getLatest(String rawTicker) {
        return getLatestByModel(rawTicker, STATE_MODEL_VERSION);
    }

    @Transactional(readOnly = true)
    public HerdObservationResponse getLatestDaily(String rawTicker) {
        return getLatestByModel(rawTicker, DAILY_MODEL_VERSION);
    }

    private HerdObservationResponse getLatestByModel(
            String rawTicker,
            String modelVersion
    ) {
        String ticker = normalizeTicker(rawTicker);
        return repository
                .findTopByTickerAndStateModelVersionOrderByObservationDateDesc(
                        ticker,
                        modelVersion
                )
                .map(row -> toResponse(row, stockRepository.findByTicker(ticker).orElse(null)))
                .orElseGet(() -> unavailable(
                        ticker,
                        stockRepository.findByTicker(ticker).orElse(null),
                        modelVersion
                ));
    }

    @Transactional(readOnly = true)
    public HerdObservationBatchResponse getLatestBatch(List<String> rawTickers) {
        List<String> tickers = normalizeBatch(rawTickers);
        Map<String, HerdObservation> observations = repository
                .findLatestByTickersAndStateModelVersion(
                        tickers,
                        STATE_MODEL_VERSION
                )
                .stream()
                .collect(Collectors.toMap(
                        HerdObservation::getTicker,
                        Function.identity()
                ));
        Map<String, Stock> stocks = stockRepository.findByTickerIn(tickers)
                .stream()
                .collect(Collectors.toMap(Stock::getTicker, Function.identity()));
        List<HerdObservationResponse> responses = tickers.stream()
                .map(ticker -> {
                    HerdObservation observation = observations.get(ticker);
                    Stock stock = stocks.get(ticker);
                    return observation == null
                            ? unavailable(ticker, stock)
                            : toResponse(observation, stock);
                })
                .toList();
        int availableCount = (int) responses.stream()
                .filter(response -> "AVAILABLE".equals(
                        response.availabilityStatus()
                ))
                .count();
        return new HerdObservationBatchResponse(
                tickers.size(),
                availableCount,
                responses
        );
    }

    @Transactional(readOnly = true)
    public HerdObservationHistoryResponse getHistory(
            String rawTicker,
            Integer requestedLimit
    ) {
        String ticker = normalizeTicker(rawTicker);
        int limit = validateLimit(requestedLimit);
        List<HerdObservationHistoryPoint> points = repository
                .findByTickerAndStateModelVersionOrderByObservationDateDesc(
                        ticker,
                        STATE_MODEL_VERSION,
                        PageRequest.of(0, limit)
                )
                .stream()
                .map(row -> new HerdObservationHistoryPoint(
                        row.getObservationDate(),
                        row.getLastObservedSession(),
                        row.getStateScore(),
                        row.getHerdStage(),
                        row.getTransitionCode(),
                        row.isTransitionEvent()
                ))
                .toList();
        return new HerdObservationHistoryResponse(
                points.isEmpty() ? "UNAVAILABLE" : "AVAILABLE",
                ticker,
                STATE_MODEL_VERSION,
                points
        );
    }

    private HerdObservationResponse toResponse(
            HerdObservation row,
            Stock stock
    ) {
        UserActionBoundary.Output action = actionBoundary.locked();
        int age = businessDaysBetween(
                row.getLastObservedSession(),
                marketSessionClock.currentSessionDate()
        );
        String freshness = age > STALE_AFTER_BUSINESS_SESSIONS
                ? "STALE"
                : "FRESH";
        return new HerdObservationResponse(
                "AVAILABLE",
                freshness,
                age,
                row.getTicker(),
                row.getDisplayLabel(),
                stock == null ? null : stock.getName(),
                stock == null ? null : stock.getSector(),
                stock == null ? null : stock.getLogoUrl(),
                row.getSourceScope(),
                row.getClaimCode(),
                row.getSchemaVersion(),
                row.getStateModelVersion(),
                row.getTransitionModelVersion(),
                row.getObservationDate(),
                row.getLastObservedSession(),
                row.getGeneratedAt().atOffset(ZoneOffset.UTC),
                row.getStateScore(),
                row.getHerdStage(),
                row.getTransitionCode(),
                row.getRawTransitionCode(),
                row.isTransitionEvent(),
                row.getDelta4w(),
                row.getDelta13w(),
                new HerdObservationResponse.FamilyScores(
                        row.getPriceExtension(),
                        row.getTrendPosition(),
                        row.getRelativePosition(),
                        row.getParticipation()
                ),
                row.getDownsideRiskContext(),
                row.getSectorEtf(),
                row.getReferenceCoverageFraction(),
                action.directionPrediction(),
                action.action(),
                action.ratio(),
                false
        );
    }

    private HerdObservationResponse unavailable(String ticker, Stock stock) {
        return unavailable(ticker, stock, STATE_MODEL_VERSION);
    }

    private HerdObservationResponse unavailable(
            String ticker,
            Stock stock,
            String modelVersion
    ) {
        UserActionBoundary.Output action = actionBoundary.locked();
        String label = "SPY".equals(ticker) ? "S&P 500 군중 상태" : null;
        return new HerdObservationResponse(
                "UNAVAILABLE",
                "UNAVAILABLE",
                null,
                ticker,
                label,
                stock == null ? null : stock.getName(),
                stock == null ? null : stock.getSector(),
                stock == null ? null : stock.getLogoUrl(),
                null,
                null,
                null,
                modelVersion,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                false,
                null,
                null,
                null,
                null,
                null,
                null,
                action.directionPrediction(),
                action.action(),
                action.ratio(),
                false
        );
    }

    private int validateLimit(Integer requestedLimit) {
        int limit = requestedLimit == null ? DEFAULT_HISTORY_LIMIT : requestedLimit;
        if (limit < 1 || limit > MAX_HISTORY_LIMIT) {
            throw new IllegalArgumentException(
                    "history limit은 1 이상 " + MAX_HISTORY_LIMIT + " 이하여야 합니다."
            );
        }
        return limit;
    }

    private String normalizeTicker(String rawTicker) {
        if (rawTicker == null || rawTicker.isBlank()) {
            throw new IllegalArgumentException("티커를 입력해주세요.");
        }
        String ticker = rawTicker.trim().toUpperCase(Locale.ROOT);
        if (!ticker.matches(TICKER_PATTERN)) {
            throw new IllegalArgumentException("올바른 미국 주식 티커 형식이 아닙니다.");
        }
        return ticker;
    }

    private List<String> normalizeBatch(List<String> rawTickers) {
        if (rawTickers == null || rawTickers.isEmpty()) {
            throw new IllegalArgumentException("조회할 티커를 입력해주세요.");
        }
        List<String> tickers = rawTickers.stream()
                .map(this::normalizeTicker)
                .distinct()
                .toList();
        if (tickers.size() > MAX_BATCH_SIZE) {
            throw new IllegalArgumentException(
                    "한 번에 최대 " + MAX_BATCH_SIZE + "종목까지 조회할 수 있습니다."
            );
        }
        return tickers;
    }

    static int businessDaysBetween(LocalDate dataDate, LocalDate today) {
        if (dataDate == null || !dataDate.isBefore(today)) return 0;
        int days = 0;
        for (
                LocalDate date = dataDate.plusDays(1);
                !date.isAfter(today);
                date = date.plusDays(1)
        ) {
            DayOfWeek day = date.getDayOfWeek();
            if (day != DayOfWeek.SATURDAY && day != DayOfWeek.SUNDAY) {
                days++;
            }
        }
        return days;
    }
}
