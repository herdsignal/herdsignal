package com.herdsignal.service;

import com.herdsignal.domain.SignalJournal;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.SignalJournalRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/** 실제 체결 기록을 기준으로 동일 방향 행동의 20거래일 쿨다운을 계산한다. */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ActionCooldownService {

    static final int COOLDOWN_TRADING_DAYS = 20;

    private final SignalJournalRepository journalRepository;
    private final DailyPriceRepository dailyPriceRepository;

    public ActionCooldownContext getContext(String userId, String ticker, LocalDate asOfDate) {
        if (userId == null || userId.isBlank() || ticker == null || ticker.isBlank() || asOfDate == null) {
            return ActionCooldownContext.none();
        }
        return new ActionCooldownContext(
                cooldown(latestAction(userId, ticker, "BUY"), asOfDate, null),
                cooldown(latestAction(userId, ticker, "SELL"), asOfDate, null)
        );
    }

    public Map<String, ActionCooldownContext> getContexts(
            String userId,
            List<String> tickers,
            Map<String, LocalDate> asOfDates
    ) {
        if (userId == null || userId.isBlank() || tickers == null || tickers.isEmpty()) {
            return Map.of();
        }

        Map<String, SignalJournal> latestByDirection = new HashMap<>();
        for (SignalJournal journal : journalRepository.findExecutedActions(userId, tickers)) {
            latestByDirection.putIfAbsent(key(journal.getTicker(), journal.getActionType()), journal);
        }

        LocalDate earliestAction = latestByDirection.values().stream()
                .map(SignalJournal::getRecordedAt)
                .filter(java.util.Objects::nonNull)
                .map(java.time.LocalDateTime::toLocalDate)
                .min(LocalDate::compareTo)
                .orElse(null);
        LocalDate latestAsOf = asOfDates.values().stream()
                .filter(java.util.Objects::nonNull)
                .max(LocalDate::compareTo)
                .orElse(null);
        List<LocalDate> observedDates = earliestAction == null || latestAsOf == null
                ? List.of()
                : dailyPriceRepository.findObservedTradingDates(earliestAction, latestAsOf);

        Map<String, ActionCooldownContext> contexts = new HashMap<>();
        for (String ticker : tickers) {
            LocalDate asOfDate = asOfDates.get(ticker);
            contexts.put(ticker, new ActionCooldownContext(
                    cooldown(Optional.ofNullable(latestByDirection.get(key(ticker, "BUY"))), asOfDate, observedDates),
                    cooldown(Optional.ofNullable(latestByDirection.get(key(ticker, "SELL"))), asOfDate, observedDates)
            ));
        }
        return Map.copyOf(contexts);
    }

    private Optional<SignalJournal> latestAction(String userId, String ticker, String actionType) {
        return journalRepository
                .findTopByUserIdAndTickerAndActionTypeAndPriceIsNotNullAndQuantityIsNotNullOrderByRecordedAtDesc(
                        userId, ticker, actionType);
    }

    private ActionCooldownContext.Cooldown cooldown(
            Optional<SignalJournal> latest,
            LocalDate asOfDate,
            List<LocalDate> prefetchedTradingDates
    ) {
        if (asOfDate == null || latest.isEmpty() || latest.get().getRecordedAt() == null) {
            return ActionCooldownContext.Cooldown.none();
        }

        LocalDate actionDate = latest.get().getRecordedAt().toLocalDate();
        if (actionDate.isAfter(asOfDate)) {
            return new ActionCooldownContext.Cooldown(true, 0, COOLDOWN_TRADING_DAYS, actionDate);
        }

        long observedDays = prefetchedTradingDates == null
                ? dailyPriceRepository.findObservedTradingDates(actionDate, asOfDate).size()
                : prefetchedTradingDates.stream()
                        .filter(date -> date.isAfter(actionDate) && !date.isAfter(asOfDate))
                        .count();
        int elapsedDays = observedDays > 0
                ? Math.toIntExact(Math.min(observedDays, Integer.MAX_VALUE))
                : countWeekdays(actionDate, asOfDate);
        int remainingDays = Math.max(0, COOLDOWN_TRADING_DAYS - elapsedDays);
        return new ActionCooldownContext.Cooldown(
                remainingDays > 0,
                elapsedDays,
                remainingDays,
                actionDate
        );
    }

    private String key(String ticker, String actionType) {
        return ticker + "|" + actionType;
    }

    private int countWeekdays(LocalDate startExclusive, LocalDate endInclusive) {
        int count = 0;
        for (LocalDate date = startExclusive.plusDays(1); !date.isAfter(endInclusive); date = date.plusDays(1)) {
            if (date.getDayOfWeek() != DayOfWeek.SATURDAY && date.getDayOfWeek() != DayOfWeek.SUNDAY) {
                count++;
            }
        }
        return count;
    }
}
