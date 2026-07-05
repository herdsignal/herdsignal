package com.herdsignal.domain;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

/**
 * 미국주식 종목 마스터 엔티티.
 * Python init_db.py의 stocks 테이블과 1:1 매핑.
 * ddl-auto: validate 이므로 컬럼명/타입이 정확히 일치해야 한다.
 */
@Entity
@Table(name = "stocks")
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Stock {

    /** PK — BIGINT AUTO_INCREMENT */
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 티커 심볼 (AAPL, NVDA 등) — UNIQUE 제약 */
    @Column(name = "ticker", nullable = false, length = 10, unique = true)
    private String ticker;

    /** 종목 정식 명칭 */
    @Column(name = "name", length = 100)
    private String name;

    /** 섹터 (Technology, Healthcare 등) */
    @Column(name = "sector", length = 50)
    private String sector;

    /** 회사 로고 URL */
    @Column(name = "logo_url", length = 300)
    private String logoUrl;

    /**
     * 시가총액 카테고리 (대형주 / 중형주 / 소형주).
     * Hibernate 기본 네이밍: marketCapCategory → market_cap_category
     */
    @Column(name = "market_cap_category", length = 20)
    private String marketCapCategory;

    /** 추적 활성 여부 — 비활성화 시 false */
    @Column(name = "is_active", nullable = false)
    @Builder.Default
    private Boolean isActive = true;

    /** 레코드 생성 시각 (UTC) — Python이 관리, Spring은 읽기 전용 */
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    /** 마지막 수정 시각 (UTC) — Python이 관리 */
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}
