package com.herdsignal.domain;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * HERD 점수 구성 지표 분해값 엔티티.
 * Python init_db.py의 herd_indicators 테이블과 1:1 매핑.
 * UNIQUE: (ticker, score_date)
 *
 * 주의: position52w 필드는 Hibernate 자동 변환으로 position52w가 되므로
 *       반드시 @Column(name = "position_52w")를 명시해야 한다.
 */
@Entity
@Table(
    name = "herd_indicators",
    uniqueConstraints = @UniqueConstraint(
        name = "uq_herd_indicators_ticker_date",
        columnNames = {"ticker", "score_date"}
    )
)
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class HerdIndicator {

    /** PK — BIGINT AUTO_INCREMENT */
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 티커 심볼 */
    @Column(name = "ticker", nullable = false, length = 10)
    private String ticker;

    /** 지표 산출 기준 날짜 */
    @Column(name = "score_date", nullable = false)
    private LocalDate scoreDate;

    /** 주봉 RSI 백분위 정규화값 (0~100) */
    @Column(name = "weekly_rsi", precision = 5, scale = 2)
    private BigDecimal weeklyRsi;

    /** 월봉 RSI 백분위 정규화값 (0~100) */
    @Column(name = "monthly_rsi", precision = 5, scale = 2)
    private BigDecimal monthlyRsi;

    /**
     * 52주 고저 위치 백분위 정규화값 (0~100).
     * DB 컬럼명: position_52w (숫자가 포함되어 자동 변환 불가 → 명시 필수)
     */
    @Column(name = "position_52w", precision = 5, scale = 2)
    private BigDecimal position52w;

    /** MA200 이격도 백분위 정규화값 (0~100) */
    @Column(name = "ma200_deviation", precision = 5, scale = 2)
    private BigDecimal ma200Deviation;

    /** 거래량 강도 백분위 정규화값 (0~100) */
    @Column(name = "volume_strength", precision = 5, scale = 2)
    private BigDecimal volumeStrength;

    /** 200주 MA 위치 백분위 정규화값 (0~100) */
    @Column(name = "ma200_weekly", precision = 5, scale = 2)
    private BigDecimal ma200Weekly;

    /** 레코드 생성 시각 (UTC) — Python이 관리, Spring은 읽기 전용 */
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;
}
