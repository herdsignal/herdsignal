package com.herdsignal.service;

import com.herdsignal.domain.DailyPrice;
import com.herdsignal.domain.HerdObservation;
import com.herdsignal.dto.HerdPriceTimelinePoint;
import com.herdsignal.dto.HerdPriceTimelineResponse;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.HerdObservationRepository;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * 가격과 S1 관찰을 market session 기준으로 결합한다.
 * 주가를 보간하거나 다른 거래일 가격으로 대체하지 않아 시점 정합성을 보존한다.
 */
@Service
public class HerdPriceTimelineService {
    static final String STATE_MODEL_VERSION = "HERD_STATE_S1";
    static final String PRICE_FIELD = "ADJUSTED_CLOSE";
    static final int DEFAULT_LIMIT = 52;
    static final int MAX_LIMIT = 260;
    private static final String TICKER_PATTERN = "^[A-Z][A-Z0-9.-]{0,9}$";

    private final HerdObservationRepository observationRepository;
    private final DailyPriceRepository priceRepository;

    public HerdPriceTimelineService(
            HerdObservationRepository observationRepository,
            DailyPriceRepository priceRepository
    ) {
        this.observationRepository = observationRepository;
        this.priceRepository = priceRepository;
    }

    @Transactional(readOnly = true)
    public HerdPriceTimelineResponse getTimeline(
            String rawTicker,
            Integer requestedLimit
    ) {
        String ticker = normalizeTicker(rawTicker);
        int limit = validateLimit(requestedLimit);
        List<HerdObservation> observations = observationRepository
                .findByTickerAndStateModelVersionOrderByObservationDateDesc(
                        ticker,
                        STATE_MODEL_VERSION,
                        PageRequest.of(0, limit)
                );
        if (observations.isEmpty()) {
            return unavailable(ticker);
        }

        LocalDate firstSession = observations.stream()
                .map(HerdObservation::getLastObservedSession)
                .min(LocalDate::compareTo)
                .orElseThrow();
        LocalDate lastSession = observations.stream()
                .map(HerdObservation::getLastObservedSession)
                .max(LocalDate::compareTo)
                .orElseThrow();
        Map<LocalDate, DailyPrice> pricesBySession = priceRepository
                .findPricesForTickerBetween(ticker, firstSession, lastSession)
                .stream()
                .collect(Collectors.toMap(
                        DailyPrice::getPriceDate,
                        Function.identity(),
                        (first, ignored) -> first
                ));

        List<HerdPriceTimelinePoint> points = observations.stream()
                .sorted(Comparator.comparing(
                        HerdObservation::getObservationDate
                ))
                .map(observation -> {
                    DailyPrice price = pricesBySession.get(
                            observation.getLastObservedSession()
                    );
                    return new HerdPriceTimelinePoint(
                            observation.getObservationDate(),
                            observation.getLastObservedSession(),
                            price == null ? null : price.getClosePrice(),
                            observation.getStateScore(),
                            observation.getHerdStage(),
                            observation.getTransitionCode(),
                            observation.isTransitionEvent()
                    );
                })
                .toList();
        int pricedCount = (int) points.stream()
                .filter(point -> point.adjustedClose() != null)
                .count();
        return new HerdPriceTimelineResponse(
                "AVAILABLE",
                ticker,
                STATE_MODEL_VERSION,
                PRICE_FIELD,
                points.size(),
                pricedCount,
                points
        );
    }

    private HerdPriceTimelineResponse unavailable(String ticker) {
        return new HerdPriceTimelineResponse(
                "UNAVAILABLE",
                ticker,
                STATE_MODEL_VERSION,
                PRICE_FIELD,
                0,
                0,
                List.of()
        );
    }

    private int validateLimit(Integer requestedLimit) {
        int limit = requestedLimit == null ? DEFAULT_LIMIT : requestedLimit;
        if (limit < 1 || limit > MAX_LIMIT) {
            throw new IllegalArgumentException(
                    "timeline limit은 1 이상 " + MAX_LIMIT + " 이하여야 합니다."
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
}
