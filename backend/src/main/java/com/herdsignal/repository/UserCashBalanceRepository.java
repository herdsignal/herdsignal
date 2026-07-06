package com.herdsignal.repository;

import com.herdsignal.domain.UserCashBalance;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

/**
 * user_cash_balance 테이블 DB 접근 인터페이스.
 */
public interface UserCashBalanceRepository extends JpaRepository<UserCashBalance, Long> {

    Optional<UserCashBalance> findByUserId(String userId);
}
