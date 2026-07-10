package com.herdsignal.repository;

import com.herdsignal.domain.HerdScore;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

/**
 * herd_scores 테이블 DB 접근 인터페이스.
 * HERD 점수 조회 전용 — 쓰기는 Python이 담당.
 */
public interface HerdScoreRepository extends JpaRepository<HerdScore, Long> {

    /** 티커의 가장 최신 날짜 HERD 점수 1건 조회 */
    Optional<HerdScore> findTopByTickerOrderByScoreDateDesc(String ticker);

    /** 티커의 전체 HERD 점수 히스토리 조회 (최신순) */
    List<HerdScore> findByTickerOrderByScoreDateDesc(String ticker);

    /** 여러 티커의 전체 히스토리를 한 번에 조회 (티커별 최신순). */
    List<HerdScore> findByTickerInOrderByTickerAscScoreDateDesc(List<String> tickers);

    /** 티커의 특정 날짜 이후 HERD 점수 히스토리 조회 (날짜 오름차순) */
    @Query("SELECT h FROM HerdScore h WHERE h.ticker = :ticker AND h.scoreDate >= :cutoff ORDER BY h.scoreDate ASC")
    List<HerdScore> findHistoryByTickerSince(@Param("ticker") String ticker, @Param("cutoff") LocalDate cutoff);
}
