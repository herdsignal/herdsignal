package com.herdsignal.repository;

import com.herdsignal.domain.SignalJournal;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

/**
 * HERD 판단 기록 저장소.
 */
public interface SignalJournalRepository extends JpaRepository<SignalJournal, Long> {

    List<SignalJournal> findByUserIdOrderByRecordedAtDesc(String userId);

    List<SignalJournal> findByUserIdAndTickerOrderByRecordedAtDesc(String userId, String ticker);

    Optional<SignalJournal> findByIdAndUserId(Long id, String userId);
}
