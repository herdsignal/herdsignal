package com.herdsignal.service;

import com.herdsignal.domain.HerdObservation;
import com.herdsignal.domain.Stock;
import com.herdsignal.domain.UserObservationReceipt;
import com.herdsignal.dto.ObservationChangeEvent;
import com.herdsignal.dto.ObservationChangesResponse;
import com.herdsignal.repository.*;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.*;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * 보유·관심 종목의 완료된 주간 S1 관찰에서 희소한 변화만 파생한다.
 * 가격 목표, 행동 방향, 개인 비중은 입력으로 사용하지 않는다.
 */
@Service
@RequiredArgsConstructor
public class ObservationChangeService {
    static final String STATE_MODEL_VERSION = "HERD_STATE_S1";
    static final int INITIAL_LOOKBACK_DAYS = 28;
    static final int MAX_UNREAD_DAYS = 364;
    static final int MAX_EVENTS = 100;
    private static final Set<String> DISPLAY_TRANSITIONS = Set.of(
            "BREAKING", "RECOVERING", "COOLING"
    );

    private final HerdObservationRepository observationRepository;
    private final UserObservationReceiptRepository receiptRepository;
    private final UserPortfolioRepository portfolioRepository;
    private final UserWatchlistRepository watchlistRepository;
    private final StockRepository stockRepository;

    @Transactional(readOnly = true)
    public ObservationChangesResponse getChanges(String userId, Integer requestedLimit) {
        int limit = validateLimit(requestedLimit);
        List<String> tickers = trackedTickers(userId);
        if (tickers.isEmpty()) {
            return new ObservationChangesResponse(null, 0, 0, List.of());
        }

        Map<String, HerdObservation> latest = observationRepository
                .findLatestByTickersAndStateModelVersion(tickers, STATE_MODEL_VERSION)
                .stream()
                .collect(Collectors.toMap(HerdObservation::getTicker, Function.identity()));
        if (latest.isEmpty()) {
            return new ObservationChangesResponse(null, tickers.size(), 0, List.of());
        }

        Map<String, LocalDate> receipts = receiptRepository.findByUserId(userId)
                .stream()
                .collect(Collectors.toMap(
                        UserObservationReceipt::getTicker,
                        UserObservationReceipt::getSeenThroughDate
                ));
        Map<String, LocalDate> effectiveCursors = effectiveCursors(latest, receipts);
        LocalDate queryFrom = effectiveCursors.values().stream()
                .min(LocalDate::compareTo)
                .orElseThrow()
                .minusDays(7);
        Map<String, Stock> stocks = stockRepository.findByTickerIn(tickers)
                .stream()
                .collect(Collectors.toMap(Stock::getTicker, Function.identity()));
        List<ObservationChangeEvent> allEvents = buildEvents(
                observationRepository.findTrackedHistorySince(
                        tickers,
                        STATE_MODEL_VERSION,
                        queryFrom
                ),
                effectiveCursors,
                receipts,
                stocks
        );
        int unreadCount = (int) allEvents.stream()
                .filter(ObservationChangeEvent::unread)
                .count();
        LocalDate generatedThrough = latest.values().stream()
                .map(HerdObservation::getObservationDate)
                .max(LocalDate::compareTo)
                .orElse(null);
        List<ObservationChangeEvent> visibleEvents = limit == 0
                ? List.of()
                : allEvents.stream().limit(limit).toList();
        return new ObservationChangesResponse(
                generatedThrough,
                tickers.size(),
                unreadCount,
                visibleEvents
        );
    }

    @Transactional
    public void markTickerSeen(String userId, String rawTicker, LocalDate seenThroughDate) {
        String ticker = normalizeTicker(rawTicker);
        requireTracked(userId, ticker);
        HerdObservation latest = observationRepository
                .findTopByTickerAndStateModelVersionOrderByObservationDateDesc(
                        ticker,
                        STATE_MODEL_VERSION
                )
                .orElseThrow(() -> new IllegalArgumentException(
                        ticker + "의 State S1 관찰값이 없습니다."
                ));
        LocalDate bounded = seenThroughDate.isAfter(latest.getObservationDate())
                ? latest.getObservationDate()
                : seenThroughDate;
        upsertReceipt(userId, ticker, bounded);
    }

    @Transactional
    public void markAllSeen(String userId) {
        List<String> tickers = trackedTickers(userId);
        if (tickers.isEmpty()) return;
        observationRepository.findLatestByTickersAndStateModelVersion(
                tickers,
                STATE_MODEL_VERSION
        ).forEach(observation -> upsertReceipt(
                userId,
                observation.getTicker(),
                observation.getObservationDate()
        ));
    }

    private List<ObservationChangeEvent> buildEvents(
            List<HerdObservation> observations,
            Map<String, LocalDate> effectiveCursors,
            Map<String, LocalDate> storedReceipts,
            Map<String, Stock> stocks
    ) {
        List<ObservationChangeEvent> events = new ArrayList<>();
        observations.stream()
                .collect(Collectors.groupingBy(HerdObservation::getTicker))
                .forEach((ticker, rows) -> {
                    rows.sort(Comparator.comparing(HerdObservation::getObservationDate));
                    LocalDate effectiveCursor = effectiveCursors.get(ticker);
                    LocalDate storedReceipt = storedReceipts.get(ticker);
                    for (int index = 1; index < rows.size(); index++) {
                        HerdObservation previous = rows.get(index - 1);
                        HerdObservation current = rows.get(index);
                        if (!current.getObservationDate().isAfter(effectiveCursor)) continue;
                        boolean transition = current.isTransitionEvent()
                                && DISPLAY_TRANSITIONS.contains(current.getTransitionCode());
                        boolean stageChanged = !Objects.equals(
                                previous.getHerdStage(),
                                current.getHerdStage()
                        );
                        if (!transition && !stageChanged) continue;
                        Stock stock = stocks.get(ticker);
                        String eventType = transition
                                ? "TRANSITION"
                                : "STAGE_CHANGE";
                        events.add(new ObservationChangeEvent(
                                ticker + ":" + current.getObservationDate() + ":" + eventType,
                                ticker,
                                stock == null ? null : stock.getName(),
                                stock == null ? null : stock.getSector(),
                                stock == null ? null : stock.getLogoUrl(),
                                current.getObservationDate(),
                                eventType,
                                current.getStateScore(),
                                current.getHerdStage(),
                                previous.getHerdStage(),
                                transition ? current.getTransitionCode() : null,
                                current.getDelta4w(),
                                storedReceipt == null
                                        || current.getObservationDate().isAfter(storedReceipt)
                        ));
                    }
                });
        events.sort(Comparator
                .comparing(ObservationChangeEvent::observationDate)
                .reversed()
                .thenComparing(ObservationChangeEvent::ticker));
        return List.copyOf(events);
    }

    private Map<String, LocalDate> effectiveCursors(
            Map<String, HerdObservation> latest,
            Map<String, LocalDate> receipts
    ) {
        return latest.entrySet().stream().collect(Collectors.toMap(
                Map.Entry::getKey,
                entry -> {
                    LocalDate latestDate = entry.getValue().getObservationDate();
                    LocalDate oldestRetained = latestDate.minusDays(MAX_UNREAD_DAYS);
                    LocalDate receipt = receipts.get(entry.getKey());
                    if (receipt == null) return latestDate.minusDays(INITIAL_LOOKBACK_DAYS);
                    return receipt.isBefore(oldestRetained) ? oldestRetained : receipt;
                }
        ));
    }

    private List<String> trackedTickers(String userId) {
        return java.util.stream.Stream.concat(
                        portfolioRepository.findByUserId(userId).stream()
                                .map(item -> item.getTicker()),
                        watchlistRepository.findByUserId(userId).stream()
                                .map(item -> item.getTicker())
                )
                .map(this::normalizeTicker)
                .distinct()
                .sorted()
                .toList();
    }

    private void requireTracked(String userId, String ticker) {
        if (!portfolioRepository.existsByUserIdAndTicker(userId, ticker)
                && !watchlistRepository.existsByUserIdAndTicker(userId, ticker)) {
            throw new IllegalArgumentException("보유 또는 관심 종목만 확인 처리할 수 있습니다.");
        }
    }

    private void upsertReceipt(String userId, String ticker, LocalDate date) {
        LocalDateTime now = LocalDateTime.now(ZoneOffset.UTC);
        UserObservationReceipt receipt = receiptRepository
                .findByUserIdAndTicker(userId, ticker)
                .orElseGet(() -> UserObservationReceipt.builder()
                        .userId(userId)
                        .ticker(ticker)
                        .createdAt(now)
                        .build());
        if (receipt.getSeenThroughDate() == null
                || date.isAfter(receipt.getSeenThroughDate())) {
            receipt.setSeenThroughDate(date);
        }
        receipt.setUpdatedAt(now);
        receiptRepository.save(receipt);
    }

    private int validateLimit(Integer requestedLimit) {
        int limit = requestedLimit == null ? 50 : requestedLimit;
        if (limit < 0 || limit > MAX_EVENTS) {
            throw new IllegalArgumentException("변화함 limit은 0 이상 100 이하여야 합니다.");
        }
        return limit;
    }

    private String normalizeTicker(String rawTicker) {
        if (rawTicker == null || rawTicker.isBlank()) {
            throw new IllegalArgumentException("티커를 입력해주세요.");
        }
        String ticker = rawTicker.trim().toUpperCase(Locale.ROOT);
        if (!ticker.matches("^[A-Z][A-Z0-9.-]{0,9}$")) {
            throw new IllegalArgumentException("올바른 미국 주식 티커 형식이 아닙니다.");
        }
        return ticker;
    }
}
