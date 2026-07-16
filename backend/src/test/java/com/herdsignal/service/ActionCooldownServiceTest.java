package com.herdsignal.service;

import com.herdsignal.domain.SignalJournal;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.SignalJournalRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ActionCooldownServiceTest {

    private SignalJournalRepository journalRepository;
    private DailyPriceRepository dailyPriceRepository;
    private ActionCooldownService service;

    @BeforeEach
    void setUp() {
        journalRepository = mock(SignalJournalRepository.class);
        dailyPriceRepository = mock(DailyPriceRepository.class);
        service = new ActionCooldownService(journalRepository, dailyPriceRepository);
    }

    @Test
    void blocksSameDirectionUntilTwentyObservedTradingDaysPass() {
        LocalDate actionDate = LocalDate.of(2026, 7, 1);
        when(journalRepository
                .findTopByUserIdAndTickerAndActionTypeAndPriceIsNotNullAndQuantityIsNotNullOrderByRecordedAtDesc(
                        "user-1", "NVDA", "BUY"))
                .thenReturn(Optional.of(journal("BUY", actionDate)));
        when(journalRepository
                .findTopByUserIdAndTickerAndActionTypeAndPriceIsNotNullAndQuantityIsNotNullOrderByRecordedAtDesc(
                        "user-1", "NVDA", "SELL"))
                .thenReturn(Optional.empty());
        when(dailyPriceRepository.findObservedTradingDates(actionDate, LocalDate.of(2026, 7, 15)))
                .thenReturn(java.util.stream.IntStream.rangeClosed(1, 9)
                        .mapToObj(actionDate::plusDays)
                        .toList());

        ActionCooldownContext context = service.getContext(
                "user-1", "NVDA", LocalDate.of(2026, 7, 15));

        assertThat(context.buy().active()).isTrue();
        assertThat(context.buy().remainingTradingDays()).isEqualTo(11);
        assertThat(context.buy().lastActionDate()).isEqualTo(actionDate);
        assertThat(context.sell().active()).isFalse();
    }

    @Test
    void releasesCooldownAfterTwentyObservedTradingDays() {
        LocalDate actionDate = LocalDate.of(2026, 6, 1);
        when(journalRepository
                .findTopByUserIdAndTickerAndActionTypeAndPriceIsNotNullAndQuantityIsNotNullOrderByRecordedAtDesc(
                        "user-1", "NVDA", "BUY"))
                .thenReturn(Optional.of(journal("BUY", actionDate)));
        when(journalRepository
                .findTopByUserIdAndTickerAndActionTypeAndPriceIsNotNullAndQuantityIsNotNullOrderByRecordedAtDesc(
                        "user-1", "NVDA", "SELL"))
                .thenReturn(Optional.empty());
        when(dailyPriceRepository.findObservedTradingDates(actionDate, LocalDate.of(2026, 7, 15)))
                .thenReturn(java.util.stream.IntStream.rangeClosed(1, 20)
                        .mapToObj(actionDate::plusDays)
                        .toList());

        ActionCooldownContext context = service.getContext(
                "user-1", "NVDA", LocalDate.of(2026, 7, 15));

        assertThat(context.buy().active()).isFalse();
        assertThat(context.buy().remainingTradingDays()).isZero();
    }

    private SignalJournal journal(String actionType, LocalDate date) {
        return SignalJournal.builder()
                .actionType(actionType)
                .recordedAt(LocalDateTime.of(date, java.time.LocalTime.NOON))
                .build();
    }
}
