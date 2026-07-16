package com.herdsignal.repository;

import com.herdsignal.domain.SignalJournal;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

/**
 * HERD 판단 기록 저장소.
 */
public interface SignalJournalRepository extends JpaRepository<SignalJournal, Long> {

    List<SignalJournal> findByUserIdOrderByRecordedAtDesc(String userId);

    List<SignalJournal> findByUserIdAndTickerOrderByRecordedAtDesc(String userId, String ticker);

    Optional<SignalJournal> findByIdAndUserId(Long id, String userId);

    Optional<SignalJournal> findTopByUserIdAndTickerAndActionTypeAndPriceIsNotNullAndQuantityIsNotNullOrderByRecordedAtDesc(
            String userId,
            String ticker,
            String actionType
    );

    @Query("""
            SELECT j
            FROM SignalJournal j
            WHERE j.userId = :userId
              AND j.ticker IN :tickers
              AND j.actionType IN ('BUY', 'SELL')
              AND j.price IS NOT NULL
              AND j.quantity IS NOT NULL
            ORDER BY j.recordedAt DESC
            """)
    List<SignalJournal> findExecutedActions(
            @Param("userId") String userId,
            @Param("tickers") List<String> tickers
    );
}
