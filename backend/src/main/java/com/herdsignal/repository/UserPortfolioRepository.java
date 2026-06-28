package com.herdsignal.repository;

import com.herdsignal.domain.UserPortfolio;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

/**
 * user_portfolio 테이블 DB 접근 인터페이스.
 * Spring이 직접 읽기/쓰기 모두 담당 (Python은 참조만).
 */
public interface UserPortfolioRepository extends JpaRepository<UserPortfolio, Long> {

    /** 사용자의 전체 보유 종목 조회 */
    List<UserPortfolio> findByUserId(String userId);

    /** 사용자의 특정 종목 조회 */
    Optional<UserPortfolio> findByUserIdAndTicker(String userId, String ticker);

    /** 사용자가 해당 종목을 보유하는지 여부 */
    boolean existsByUserIdAndTicker(String userId, String ticker);
}
