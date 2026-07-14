package com.herdsignal.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/** 사용자별 Action Layer 해석 설정. */
@Entity
@Table(name = "investor_profiles")
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class InvestorProfile {
    @Id
    @Column(name = "user_id", length = 50)
    private String userId;

    @Column(nullable = false, length = 30)
    private String strategy;

    @Column(name = "risk_tolerance", nullable = false, length = 20)
    private String riskTolerance;

    @Column(name = "time_horizon_years", nullable = false)
    private Integer timeHorizonYears;

    @Column(name = "liquidity_buffer_months", nullable = false)
    private Integer liquidityBufferMonths;

    @Column(name = "max_action_ratio", nullable = false, precision = 5, scale = 4)
    private BigDecimal maxActionRatio;

    @Column(name = "target_equity_ratio", nullable = false, precision = 5, scale = 4)
    private BigDecimal targetEquityRatio;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    @PrePersist
    void onCreate() {
        LocalDateTime now = LocalDateTime.now();
        createdAt = createdAt == null ? now : createdAt;
        updatedAt = now;
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = LocalDateTime.now();
    }
}
