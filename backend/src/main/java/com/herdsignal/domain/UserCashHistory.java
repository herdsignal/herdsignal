package com.herdsignal.domain;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 사용자 현금 보유액 일별 스냅샷.
 * 총자산 히스토리에서 주식 평가액과 합산한다.
 */
@Entity
@Table(
    name = "user_cash_history",
    uniqueConstraints = @UniqueConstraint(
        name = "uq_user_cash_history_user_date",
        columnNames = {"user_id", "snapshot_date"}
    )
)
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserCashHistory {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 사용자 ID */
    @Column(name = "user_id", nullable = false, length = 50)
    private String userId;

    /** 스냅샷 기준일 */
    @Column(name = "snapshot_date", nullable = false)
    private LocalDate snapshotDate;

    /** 현금 보유액 (USD) */
    @Column(name = "cash_amount", nullable = false, precision = 15, scale = 2)
    private BigDecimal cashAmount;

    /** 레코드 생성 시각 */
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    /** 마지막 수정 시각 */
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}
