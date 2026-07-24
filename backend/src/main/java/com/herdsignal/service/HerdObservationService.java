package com.herdsignal.service;

import com.herdsignal.domain.HerdObservation;
import com.herdsignal.dto.HerdObservationHistoryPoint;
import com.herdsignal.dto.HerdObservationHistoryResponse;
import com.herdsignal.dto.HerdObservationResponse;
import com.herdsignal.repository.HerdObservationRepository;
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

@Service
public class HerdObservationService {
    static final String STATE_MODEL_VERSION = "HERD_STATE_S1";
    static final int DEFAULT_HISTORY_LIMIT = 52;
    static final int MAX_HISTORY_LIMIT = 260;
    private static final int STALE_AFTER_BUSINESS_SESSIONS = 2;
    private static final String TICKER_PATTERN = "^[A-Z][A-Z0-9.-]{0,9}$";
    private static final BigDecimal ZERO_RATIO = new BigDecimal("0.0000");

    private final HerdObservationRepository repository;
    private final UsMarketSessionClock marketSessionClock;

    @Autowired
    public HerdObservationService(
            HerdObservationRepository repository,
            UsMarketSessionClock marketSessionClock
    ) {
        this.repository = repository;
        this.marketSessionClock = marketSessionClock;
    }

    @Transactional(readOnly = true)
    public HerdObservationResponse getLatest(String rawTicker) {
        String ticker = normalizeTicker(rawTicker);
        return repository
                .findTopByTickerAndStateModelVersionOrderByObservationDateDesc(
                        ticker,
                        STATE_MODEL_VERSION
                )
                .map(this::toResponse)
                .orElseGet(() -> unavailable(ticker));
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

    private HerdObservationResponse toResponse(HerdObservation row) {
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
                false,
                "HOLD",
                ZERO_RATIO,
                false
        );
    }

    private HerdObservationResponse unavailable(String ticker) {
        String label = "SPY".equals(ticker) ? "S&P 500 군중 상태" : null;
        return new HerdObservationResponse(
                "UNAVAILABLE",
                "UNAVAILABLE",
                null,
                ticker,
                label,
                null,
                null,
                null,
                STATE_MODEL_VERSION,
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
                false,
                "HOLD",
                ZERO_RATIO,
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
