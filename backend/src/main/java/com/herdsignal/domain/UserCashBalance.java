package com.herdsignal.domain;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 사용자 현금 보유액 현재값.
 * MVP에서는 user_id='local' 1개 행을 기준으로 사용한다.
 */
@Entity
@Table(name = "user_cash_balance")
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserCashBalance {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 사용자 ID */
    @Column(name = "user_id", nullable = false, unique = true, length = 50)
    private String userId;

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
