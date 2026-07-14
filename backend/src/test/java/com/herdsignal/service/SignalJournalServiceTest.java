package com.herdsignal.service;

import com.herdsignal.domain.SignalJournal;
import com.herdsignal.exception.ResourceNotFoundException;
import com.herdsignal.repository.DailyPriceRepository;
import com.herdsignal.repository.SignalJournalRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class SignalJournalServiceTest {
    private SignalJournalRepository repository;
    private SignalJournalService service;

    @BeforeEach
    void setUp() {
        repository = mock(SignalJournalRepository.class);
        service = new SignalJournalService(repository, mock(DailyPriceRepository.class));
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
}
