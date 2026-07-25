package com.herdsignal.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/** 운영 행동 승격 요청과 승인·거절 사유를 보존하는 불변 감사 행. */
@Entity
@Table(
        name = "model_promotion_audits",
        indexes = @Index(
                name = "ix_model_promotion_audits_candidate_time",
                columnList = "candidate_id,requested_at"
        )
)
@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ModelPromotionAudit {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "candidate_id", nullable = false, length = 80)
    private String candidateId;

    @Column(name = "model_version", length = 80)
    private String modelVersion;

    @Column(name = "artifact_sha256", length = 64, columnDefinition = "CHAR(64)")
    private String artifactSha256;

    @Column(length = 10)
    private String ticker;

    @Column(name = "requested_action", length = 10)
    private String requestedAction;

    @Column(name = "requested_ratio", precision = 6, scale = 4)
    private BigDecimal requestedRatio;

    @Column(nullable = false, length = 20)
    private String decision;

    @Column(name = "reason_code", nullable = false, length = 80)
    private String reasonCode;

    @Column(name = "policy_version", length = 40)
    private String policyVersion;

    @Column(length = 100)
    private String reviewer;

    @Column(name = "approval_file_sha256", length = 64, columnDefinition = "CHAR(64)")
    private String approvalFileSha256;

    @Column(name = "approved_at")
    private LocalDateTime approvedAt;

    @Column(name = "requested_at", nullable = false, updatable = false)
    private LocalDateTime requestedAt;
}
