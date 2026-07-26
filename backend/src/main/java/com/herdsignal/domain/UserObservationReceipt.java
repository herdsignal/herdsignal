package com.herdsignal.domain;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDate;
import java.time.LocalDateTime;

/** 사용자가 종목별 State S1 변화를 확인한 마지막 관찰일. */
@Entity
@Table(
        name = "user_observation_receipts",
        uniqueConstraints = @UniqueConstraint(
                name = "uq_observation_receipt_user_ticker",
                columnNames = {"user_id", "ticker"}
        ),
        indexes = @Index(
                name = "ix_observation_receipt_user",
                columnList = "user_id"
        )
)
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserObservationReceipt {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false, length = 50)
    private String userId;

    @Column(nullable = false, length = 10)
    private String ticker;

    @Column(name = "seen_through_date", nullable = false)
    private LocalDate seenThroughDate;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;
}
