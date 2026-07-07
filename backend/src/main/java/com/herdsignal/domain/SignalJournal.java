package com.herdsignal.domain;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * HERD 판단 기록 엔티티.
 * 사용자가 종목 상세에서 남긴 매수/보류/익절 판단을 장기 보관한다.
 */
@Entity
@Table(
        name = "signal_journal",
        indexes = {
                @Index(name = "ix_signal_journal_user_recorded", columnList = "user_id, recorded_at"),
                @Index(name = "ix_signal_journal_user_ticker_recorded", columnList = "user_id, ticker, recorded_at")
        }
)
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SignalJournal {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false, length = 50)
    @Builder.Default
    private String userId = "local";

    @Column(name = "ticker", nullable = false, length = 10)
    private String ticker;

    @Column(name = "action_type", nullable = false, length = 20)
    private String actionType;

    @Column(name = "action_label", length = 50)
    private String actionLabel;

    @Column(name = "score_date")
    private LocalDate scoreDate;

    @Column(name = "herd_score", precision = 5, scale = 2)
    private BigDecimal herdScore;

    @Column(name = "herd_stage", length = 20)
    private String herdStage;

    @Column(name = "signal", length = 20)
    private String signal;

    @Column(name = "signal_label", length = 100)
    private String signalLabel;

    @Column(name = "action_ratio", precision = 6, scale = 4)
    private BigDecimal actionRatio;

    @Column(name = "signal_duration_days")
    private Long signalDurationDays;

    @Column(name = "stage_duration_days")
    private Long stageDurationDays;

    @Column(name = "price", precision = 12, scale = 4)
    private BigDecimal price;

    @Column(name = "quantity", precision = 12, scale = 4)
    private BigDecimal quantity;

    @Column(name = "amount", precision = 15, scale = 2)
    private BigDecimal amount;

    @Column(name = "profit_pct", precision = 8, scale = 4)
    private BigDecimal profitPct;

    @Column(name = "memo", length = 1000)
    private String memo;

    @Column(name = "recorded_at", nullable = false)
    private LocalDateTime recordedAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}
