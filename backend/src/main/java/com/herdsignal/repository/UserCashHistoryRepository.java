package com.herdsignal.repository;

import com.herdsignal.domain.UserCashHistory;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

/**
 * user_cash_history 테이블 DB 접근 인터페이스.
 */
public interface UserCashHistoryRepository extends JpaRepository<UserCashHistory, Long> {

    Optional<UserCashHistory> findByUserIdAndSnapshotDate(String userId, LocalDate snapshotDate);

    Optional<UserCashHistory> findTopByUserIdAndSnapshotDateBeforeOrderBySnapshotDateDesc(
            String userId, LocalDate snapshotDate);

    Optional<UserCashHistory> findTopByUserIdOrderBySnapshotDateDesc(String userId);

    List<UserCashHistory> findByUserIdAndSnapshotDateBetweenOrderBySnapshotDateAsc(
            String userId, LocalDate start, LocalDate end);

}
