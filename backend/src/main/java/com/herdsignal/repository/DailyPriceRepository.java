package com.herdsignal.repository;

import com.herdsignal.domain.DailyPrice;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

/**
 * daily_prices 테이블 읽기 전용 접근 인터페이스.
 * Spring Boot는 현재가(최신 종가) 조회 목적으로만 사용.
 * 쓰기는 Python 스케줄러가 담당.
 */
public interface DailyPriceRepository extends JpaRepository<DailyPrice, Long> {

    /**
     * 특정 종목의 최신 2일치 종가 조회 (오늘 + 전일).
     * 현재가 + 일일 등락률 계산에 사용.
     * 결과: price_date DESC 정렬 — [0]=최신, [1]=전일
     */
    List<DailyPrice> findTop2ByTickerOrderByPriceDateDesc(String ticker);
}
