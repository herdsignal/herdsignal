package com.herdsignal.repository;

import com.herdsignal.domain.Stock;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

/**
 * stocks 테이블 DB 접근 인터페이스.
 * 종목 마스터 조회 전용 — 쓰기는 Python이 담당.
 */
public interface StockRepository extends JpaRepository<Stock, Long> {

    /** 티커로 단일 종목 조회 */
    Optional<Stock> findByTicker(String ticker);

    /** 추적 활성 종목 전체 조회 */
    List<Stock> findByIsActiveTrue();
}
