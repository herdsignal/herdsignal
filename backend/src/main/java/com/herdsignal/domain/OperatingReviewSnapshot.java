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
import java.time.LocalDate;
import java.time.LocalDateTime;

/** 명시적 기록 시점의 장기 운용 판단. 애플리케이션에는 수정 경로가 없다. */
@Entity
@Table(name = "operating_review_snapshots", indexes = {
        @Index(name = "ix_operating_review_user_ticker_time", columnList = "user_id,ticker,reviewed_at"),
        @Index(name = "ix_operating_review_ticker_observation", columnList = "ticker,observation_date")
})
@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class OperatingReviewSnapshot {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false, length = 50)
    private String userId;

    @Column(nullable = false, length = 10)
    private String ticker;

    @Column(name = "reviewed_at", nullable = false)
    private LocalDateTime reviewedAt;

    @Column(name = "observation_date")
    private LocalDate observationDate;

    @Column(name = "reference_price_date")
    private LocalDate referencePriceDate;

    @Column(name = "reference_price", precision = 12, scale = 4)
    private BigDecimal referencePrice;

    @Column(name = "decision_code", nullable = false, length = 30)
    private String decisionCode;

    @Column(name = "action_authorized", nullable = false)
    private boolean actionAuthorized;

    @Column(name = "action_ratio", nullable = false, precision = 7, scale = 6)
    private BigDecimal actionRatio;

    @Column(name = "evidence_schema_version", nullable = false, length = 30)
    private String evidenceSchemaVersion;

    @Column(name = "decision_model_version", nullable = false, length = 50)
    private String decisionModelVersion;

    @Column(name = "payload_json", nullable = false, columnDefinition = "LONGTEXT")
    private String payloadJson;

    @Column(name = "payload_sha256", nullable = false, length = 64, columnDefinition = "CHAR(64)")
    private String payloadSha256;

    @Column(name = "record_sha256", length = 64, columnDefinition = "CHAR(64)")
    private String recordSha256;
}
