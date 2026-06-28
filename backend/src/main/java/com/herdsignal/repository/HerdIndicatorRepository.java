package com.herdsignal.repository;

import com.herdsignal.domain.HerdIndicator;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

/**
 * herd_indicators 테이블 DB 접근 인터페이스.
 * HERD 지표 분해값 조회 전용 — 쓰기는 Python이 담당.
 */
public interface HerdIndicatorRepository extends JpaRepository<HerdIndicator, Long> {

    /** 티커의 가장 최신 날짜 지표 분해값 1건 조회 */
    Optional<HerdIndicator> findTopByTickerOrderByScoreDateDesc(String ticker);
}
