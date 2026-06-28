package com.herdsignal.domain;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 사용자 보유 종목 엔티티.
 * Python init_db.py의 user_portfolio 테이블과 1:1 매핑.
 * UNIQUE: (user_id, ticker)
 */
@Entity
@Table(
    name = "user_portfolio",
    uniqueConstraints = @UniqueConstraint(
        name = "uq_portfolio_user_ticker",
        columnNames = {"user_id", "ticker"}
    )
)
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserPortfolio {

    /** PK — BIGINT AUTO_INCREMENT */
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 사용자 ID — MVP 단계에서는 'local' 고정 */
    @Column(name = "user_id", nullable = false, length = 50)
    @Builder.Default
    private String userId = "local";

    /** 티커 심볼 */
    @Column(name = "ticker", nullable = false, length = 10)
    private String ticker;

    /** 평균 매수가 (USD) */
    @Column(name = "avg_price", precision = 12, scale = 4)
    private BigDecimal avgPrice;

    /** 보유 수량 (소수점 지원) */
    @Column(name = "quantity", precision = 12, scale = 4)
    private BigDecimal quantity;

    /** 메모 */
    @Column(name = "memo", length = 200)
    private String memo;

    /** 레코드 생성 시각 (UTC) — Python이 관리, Spring은 읽기 전용 */
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    /** 마지막 수정 시각 (UTC) — Python이 관리 */
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}
