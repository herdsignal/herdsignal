package com.herdsignal.domain;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 날짜별 HERD Index 점수 엔티티.
 * Python init_db.py의 herd_scores 테이블과 1:1 매핑.
 * UNIQUE: (ticker, score_date)
 *
 * 주의: signal은 MariaDB 예약어 — Hibernate 6의 MariaDB 방언이 자동 쿼팅 처리.
 */
@Entity
@Table(
    name = "herd_scores",
    uniqueConstraints = @UniqueConstraint(
        name = "uq_herd_scores_ticker_date",
        columnNames = {"ticker", "score_date"}
    )
)
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class HerdScore {

    /** PK — BIGINT AUTO_INCREMENT */
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 티커 심볼 */
    @Column(name = "ticker", nullable = false, length = 10)
    private String ticker;

    /** 점수 산출 기준 날짜 */
    @Column(name = "score_date", nullable = false)
    private LocalDate scoreDate;

    /** HERD 점수 (0.00 ~ 100.00) */
    @Column(name = "herd_score", nullable = false, precision = 5, scale = 2)
    private BigDecimal herdScore;

    /** 단계 (Herd Flee / Scatter / Calm / Drift / Rush) */
    @Column(name = "herd_stage", nullable = false, length = 20)
    private String herdStage;

    /**
     * 매매 신호 (BUY / SELL / HOLD / ADD / REDUCE).
     * signal은 MariaDB 예약어이므로 명시적 @Column으로 매핑.
     */
    @Column(name = "signal", length = 20)
    private String signal;

    /** 레코드 생성 시각 (UTC) — Python이 관리, Spring은 읽기 전용 */
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;
}
