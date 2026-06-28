package com.herdsignal.repository;

import com.herdsignal.domain.HerdScore;
import org.springframework.data.jpa.repository.JpaRepository;

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
}
