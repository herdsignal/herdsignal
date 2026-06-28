package com.herdsignal.repository;

import com.herdsignal.domain.UserWatchlist;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

/**
 * user_watchlist 테이블 DB 접근 인터페이스.
 * Spring이 직접 읽기/쓰기 담당.
 */
public interface UserWatchlistRepository extends JpaRepository<UserWatchlist, Long> {

    /** 사용자의 전체 관심 종목 조회 */
    List<UserWatchlist> findByUserId(String userId);

    /** 사용자의 특정 관심 종목 조회 */
    Optional<UserWatchlist> findByUserIdAndTicker(String userId, String ticker);

    /** 사용자가 해당 종목을 관심 종목으로 등록했는지 여부 */
    boolean existsByUserIdAndTicker(String userId, String ticker);
}
