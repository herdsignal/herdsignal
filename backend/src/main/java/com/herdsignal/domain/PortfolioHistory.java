package com.herdsignal.domain;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 포트폴리오 일별 평가금액 스냅샷 엔티티.
 * Python 스케줄러가 매일 HERD 계산 완료 후 portfolio_history 테이블에 저장.
 * Spring Boot는 읽기 전용으로 사용 (히스토리 조회 + 요약 집계용).
 * UNIQUE: (user_id, snapshot_date) — 날짜당 1개 레코드 보장.
 */
@Entity
@Table(
    name = "portfolio_history",
    uniqueConstraints = @UniqueConstraint(
        name = "uq_portfolio_history_user_date",
        columnNames = {"user_id", "snapshot_date"}
    )
)
@Getter
@NoArgsConstructor
public class PortfolioHistory {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 사용자 ID */
    @Column(name = "user_id", nullable = false, length = 50)
    private String userId;

    /** 스냅샷 기준일 */
    @Column(name = "snapshot_date", nullable = false)
    private LocalDate snapshotDate;

    /** 총 평가금액 (USD) */
    @Column(name = "total_value", nullable = false, precision = 15, scale = 2)
    private BigDecimal totalValue;

    /** 총 매입금액 (USD) */
    @Column(name = "total_cost", nullable = false, precision = 15, scale = 2)
    private BigDecimal totalCost;

    /** 총 수익률 (%) */
    @Column(name = "total_return_pct", nullable = false, precision = 8, scale = 4)
    private BigDecimal totalReturnPct;

    /** 레코드 생성 시각 (UTC) */
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;
}
