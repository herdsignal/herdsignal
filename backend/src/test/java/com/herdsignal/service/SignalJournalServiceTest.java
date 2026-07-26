package com.herdsignal.service;

import com.herdsignal.domain.SignalJournal;
import com.herdsignal.exception.ResourceNotFoundException;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.SignalJournalRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class SignalJournalServiceTest {
    private SignalJournalRepository repository;
    private DailyPriceRepository dailyPriceRepository;
    private SignalJournalService service;

    @BeforeEach
    void setUp() {
        repository = mock(SignalJournalRepository.class);
        dailyPriceRepository = mock(DailyPriceRepository.class);
        service = new SignalJournalService(
                repository,
                dailyPriceRepository,
                new UserActionBoundary(),
                new SignalJournalOutcomeService(dailyPriceRepository)
        );
    }

    @Test
    void cannotDeleteAnotherUsersJournal() {
        when(repository.findByIdAndUserId(7L, "user-b")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.deleteJournal("user-b", 7L))
                .isInstanceOf(ResourceNotFoundException.class);

        verify(repository, never()).delete(org.mockito.ArgumentMatchers.any());
    }

    @Test
    void ownerCanDeleteJournal() {
        SignalJournal journal = SignalJournal.builder().id(7L).userId("user-a").ticker("NVDA").build();
        when(repository.findByIdAndUserId(7L, "user-a")).thenReturn(Optional.of(journal));

        service.deleteJournal("user-a", 7L);

        verify(repository).delete(journal);
    }

    @Test
    void sanitizesClientModelSignalButPreservesManualActionType() {
        var request = new com.herdsignal.dto.SignalJournalRequest();
        org.springframework.test.util.ReflectionTestUtils.setField(request, "ticker", "nvda");
        org.springframework.test.util.ReflectionTestUtils.setField(request, "actionType", "SELL");
        org.springframework.test.util.ReflectionTestUtils.setField(
                request, "actionLabel", "내 판단으로 일부 익절"
        );
        org.springframework.test.util.ReflectionTestUtils.setField(request, "signal", "SELL");
        org.springframework.test.util.ReflectionTestUtils.setField(request, "signalLabel", "강한 익절");
        org.springframework.test.util.ReflectionTestUtils.setField(
                request, "actionRatio", new java.math.BigDecimal("0.15")
        );
        org.springframework.test.util.ReflectionTestUtils.setField(request, "signalDurationDays", 8L);
        when(repository.save(any(SignalJournal.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        var response = service.createJournal("user-a", request);

        var saved = org.mockito.ArgumentCaptor.forClass(SignalJournal.class);
        verify(repository).save(saved.capture());
        assertThat(saved.getValue().getActionType()).isEqualTo("SELL");
        assertThat(saved.getValue().getSignal()).isEqualTo("HOLD");
        assertThat(saved.getValue().getActionRatio()).isZero();
        assertThat(saved.getValue().getSignalDurationDays()).isNull();
        assertThat(response.getActionType()).isEqualTo("SELL");
        assertThat(response.getSignal()).isEqualTo("HOLD");
        assertThat(response.getActionRatio()).isZero();
    }

    @Test
    void sanitizesHistoricalResearchSignalsOnRead() {
        SignalJournal historical = SignalJournal.builder()
                .id(3L)
                .userId("user-a")
                .ticker("TSLA")
                .actionType("BUY")
                .signal("BUY")
                .signalLabel("과거 연구 신호")
                .actionRatio(new java.math.BigDecimal("0.10"))
                .signalDurationDays(4L)
                .build();
        when(repository.findByUserIdOrderByRecordedAtDesc("user-a"))
                .thenReturn(java.util.List.of(historical));

        var response = service.getJournals("user-a", null).get(0);

        assertThat(response.getActionType()).isEqualTo("BUY");
        assertThat(response.getSignal()).isEqualTo("HOLD");
        assertThat(response.getActionRatio()).isZero();
        assertThat(response.getSignalDurationDays()).isNull();
    }
}
