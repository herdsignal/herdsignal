package com.herdsignal.repository;

import com.herdsignal.domain.HerdIndicator;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

/**
 * herd_indicators 테이블 DB 접근 인터페이스.
 * HERD 지표 분해값 조회 전용 — 쓰기는 Python이 담당.
 */
public interface HerdIndicatorRepository extends JpaRepository<HerdIndicator, Long> {

    /** 티커의 가장 최신 날짜 지표 분해값 1건 조회 */
    Optional<HerdIndicator> findTopByTickerOrderByScoreDateDesc(String ticker);

    /** 여러 티커의 최신 지표만 일괄 조회한다. */
    @Query("""
            SELECT h FROM HerdIndicator h
            WHERE h.ticker IN :tickers
              AND h.scoreDate = (
                  SELECT MAX(latest.scoreDate)
                  FROM HerdIndicator latest
                  WHERE latest.ticker = h.ticker
              )
            """)
    List<HerdIndicator> findLatestByTickers(@Param("tickers") List<String> tickers);
}
