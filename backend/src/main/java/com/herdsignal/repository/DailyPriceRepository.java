package com.herdsignal.repository;

import com.herdsignal.domain.DailyPrice;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

/**
 * daily_prices 테이블 읽기 전용 접근 인터페이스.
 * Spring Boot는 현재가(최신 종가) 조회 목적으로만 사용.
 * 쓰기는 Python 스케줄러가 담당.
 */
public interface DailyPriceRepository extends JpaRepository<DailyPrice, Long> {

    @Query("SELECT MAX(d.priceDate) FROM DailyPrice d")
    Optional<LocalDate> findLatestPriceDate();

    /**
     * 특정 종목의 최신 2일치 종가 조회 (오늘 + 전일).
     * 현재가 + 일일 등락률 계산에 사용.
     * 결과: price_date DESC 정렬 — [0]=최신, [1]=전일
     */
    List<DailyPrice> findTop2ByTickerOrderByPriceDateDesc(String ticker);

    /**
     * 특정 기준일 이하의 최신 종가 조회.
     * KST 22:30 미국장 시작 기준 "오늘" 가격 계산에 사용.
     */
    Optional<DailyPrice> findTopByTickerAndPriceDateLessThanEqualAndClosePriceIsNotNullOrderByPriceDateDesc(
            String ticker,
            LocalDate priceDate
    );

    /**
     * 특정 거래일 이전의 최신 종가 조회.
     * KST 22:30 미국장 시작 기준 전 거래일 비교에 사용.
     */
    Optional<DailyPrice> findTopByTickerAndPriceDateLessThanAndClosePriceIsNotNullOrderByPriceDateDesc(
            String ticker,
            LocalDate priceDate
    );

    @Query("""
            SELECT DISTINCT d.priceDate
            FROM DailyPrice d
            WHERE d.priceDate > :startDate
              AND d.priceDate <= :endDate
            ORDER BY d.priceDate
            """)
    List<LocalDate> findObservedTradingDates(
            @Param("startDate") LocalDate startDate,
            @Param("endDate") LocalDate endDate
    );

    @Query("""
            SELECT d
            FROM DailyPrice d
            WHERE d.ticker IN :tickers
              AND d.closePrice IS NOT NULL
              AND d.priceDate = (
                  SELECT MAX(d2.priceDate)
                  FROM DailyPrice d2
                  WHERE d2.ticker = d.ticker
                    AND d2.closePrice IS NOT NULL
              )
            """)
    List<DailyPrice> findLatestByTickers(@Param("tickers") List<String> tickers);
}
