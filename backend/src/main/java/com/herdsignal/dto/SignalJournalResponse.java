package com.herdsignal.dto;

import com.herdsignal.domain.SignalJournal;
import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * HERD 판단 기록 응답 DTO.
 */
@Getter
@Builder
public class SignalJournalResponse {

    private Long id;
    private String ticker;
    private String actionType;
    private String actionLabel;
    private LocalDate scoreDate;
    private BigDecimal herdScore;
    private String herdStage;
    private String signal;
    private String signalLabel;
    private BigDecimal actionRatio;
    private Long signalDurationDays;
    private Long stageDurationDays;
    private BigDecimal price;
    private BigDecimal quantity;
    private BigDecimal amount;
    private BigDecimal profitPct;
    private String memo;
    private LocalDateTime recordedAt;
    private LocalDateTime createdAt;

    public static SignalJournalResponse from(SignalJournal journal) {
        return SignalJournalResponse.builder()
                .id(journal.getId())
                .ticker(journal.getTicker())
                .actionType(journal.getActionType())
                .actionLabel(journal.getActionLabel())
                .scoreDate(journal.getScoreDate())
                .herdScore(journal.getHerdScore())
                .herdStage(journal.getHerdStage())
                .signal(journal.getSignal())
                .signalLabel(journal.getSignalLabel())
                .actionRatio(journal.getActionRatio())
                .signalDurationDays(journal.getSignalDurationDays())
                .stageDurationDays(journal.getStageDurationDays())
                .price(journal.getPrice())
                .quantity(journal.getQuantity())
                .amount(journal.getAmount())
                .profitPct(journal.getProfitPct())
                .memo(journal.getMemo())
                .recordedAt(journal.getRecordedAt())
                .createdAt(journal.getCreatedAt())
                .build();
    }
}
