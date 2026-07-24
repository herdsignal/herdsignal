package com.herdsignal.domain;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * State S1·Transition S1 관찰 스냅샷.
 *
 * <p>Python이 쓰고 Spring은 읽기만 한다. v4 {@code herd_scores}와
 * 생명주기 및 의미를 공유하지 않는다.</p>
 */
@Entity
@Table(
        name = "herd_observations",
        uniqueConstraints = @UniqueConstraint(
                name = "uq_herd_observations_model_date",
                columnNames = {"ticker", "state_model_version", "observation_date"}
        ),
        indexes = {
                @Index(
                        name = "ix_herd_observations_ticker_latest",
                        columnList = "ticker,state_model_version,observation_date"
                ),
                @Index(
                        name = "ix_herd_observations_generated_at",
                        columnList = "generated_at"
                )
        }
)
@Getter
@Builder(toBuilder = true)
@NoArgsConstructor
@AllArgsConstructor
public class HerdObservation {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 10)
    private String ticker;

    @Column(name = "schema_version", nullable = false, length = 60)
    private String schemaVersion;

    @Column(name = "state_model_version", nullable = false, length = 40)
    private String stateModelVersion;

    @Column(name = "transition_model_version", nullable = false, length = 40)
    private String transitionModelVersion;

    @Column(name = "observation_date", nullable = false)
    private LocalDate observationDate;

    @Column(name = "last_observed_session", nullable = false)
    private LocalDate lastObservedSession;

    @Column(name = "generated_at", nullable = false)
    private LocalDateTime generatedAt;

    @Column(name = "source_scope", nullable = false, length = 30)
    private String sourceScope;

    @Column(name = "display_label", length = 100)
    private String displayLabel;

    @Column(name = "claim_code", length = 60)
    private String claimCode;

    @Column(name = "state_score", nullable = false, precision = 7, scale = 4)
    private BigDecimal stateScore;

    @Column(name = "herd_stage", nullable = false, length = 20)
    private String herdStage;

    @Column(name = "transition_code", nullable = false, length = 30)
    private String transitionCode;

    @Column(name = "raw_transition_code", nullable = false, length = 30)
    private String rawTransitionCode;

    @Column(name = "transition_event", nullable = false)
    private boolean transitionEvent;

    @Column(name = "delta_4w", nullable = false, precision = 8, scale = 4)
    private BigDecimal delta4w;

    @Column(name = "delta_13w", nullable = false, precision = 8, scale = 4)
    private BigDecimal delta13w;

    @Column(name = "price_extension", nullable = false, precision = 7, scale = 4)
    private BigDecimal priceExtension;

    @Column(name = "trend_position", nullable = false, precision = 7, scale = 4)
    private BigDecimal trendPosition;

    @Column(name = "relative_position", nullable = false, precision = 7, scale = 4)
    private BigDecimal relativePosition;

    @Column(nullable = false, precision = 7, scale = 4)
    private BigDecimal participation;

    @Column(name = "downside_risk_context", nullable = false, precision = 7, scale = 4)
    private BigDecimal downsideRiskContext;

    @Column(name = "sector_etf", nullable = false, length = 10)
    private String sectorEtf;

    @Column(name = "reference_coverage_fraction", precision = 7, scale = 6)
    private BigDecimal referenceCoverageFraction;

    @Column(name = "direction_prediction", nullable = false)
    private boolean directionPrediction;

    @Column(name = "operational_action", nullable = false, length = 10)
    private String operationalAction;

    @Column(name = "operational_action_ratio", nullable = false, precision = 6, scale = 4)
    private BigDecimal operationalActionRatio;

    @Column(name = "survivorship_safe", nullable = false)
    private boolean survivorshipSafe;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}
