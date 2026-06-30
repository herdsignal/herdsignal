package com.herdsignal.domain;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 일봉 OHLCV 데이터 엔티티.
 * Python 스케줄러가 매일 yfinance에서 수집해 daily_prices 테이블에 저장.
 * Spring Boot는 읽기 전용으로 사용 (현재가 조회용).
 */
@Entity
@Table(name = "daily_prices")
@Getter
@NoArgsConstructor
public class DailyPrice {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 티커 심볼 */
    @Column(name = "ticker", nullable = false, length = 10)
    private String ticker;

    /** 거래일 날짜 */
    @Column(name = "price_date", nullable = false)
    private LocalDate priceDate;

    /** 시가 */
    @Column(name = "open_price", precision = 12, scale = 4)
    private BigDecimal openPrice;

    /** 고가 */
    @Column(name = "high_price", precision = 12, scale = 4)
    private BigDecimal highPrice;

    /** 저가 */
    @Column(name = "low_price", precision = 12, scale = 4)
    private BigDecimal lowPrice;

    /** 종가 (수정 종가) — 현재가 조회에 사용 */
    @Column(name = "close_price", precision = 12, scale = 4)
    private BigDecimal closePrice;

    /** 거래량 */
    @Column(name = "volume")
    private Long volume;

    /** 레코드 생성 시각 (UTC) */
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;
}
