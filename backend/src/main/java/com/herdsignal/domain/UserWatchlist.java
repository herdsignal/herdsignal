package com.herdsignal.domain;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

/**
 * 사용자 관심 종목 엔티티.
 * Python init_db.py의 user_watchlist 테이블과 1:1 매핑.
 * UNIQUE: (user_id, ticker)
 */
@Entity
@Table(
    name = "user_watchlist",
    uniqueConstraints = @UniqueConstraint(
        name = "uq_watchlist_user_ticker",
        columnNames = {"user_id", "ticker"}
    )
)
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserWatchlist {

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

    /** 메모 (선택) */
    @Column(name = "memo", length = 200)
    private String memo;

    /** 레코드 생성 시각 (UTC) — Python이 관리, Spring 저장 시 직접 설정 */
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;
}
