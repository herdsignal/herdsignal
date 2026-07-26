package com.herdsignal.dto;

import com.herdsignal.domain.SignalJournal;
import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

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
    private LocalDate observationDate;
    private LocalDate referencePriceDate;
    private BigDecimal referencePrice;
    private List<JournalHorizonOutcomeResponse> horizonOutcomes;
    private String memo;
    private LocalDateTime recordedAt;
    private LocalDateTime createdAt;

    public static SignalJournalResponse from(
            SignalJournal journal,
            String operationalAction,
            BigDecimal operationalActionRatio,
            LocalDate observationDate,
            LocalDate referencePriceDate,
            BigDecimal referencePrice,
            List<JournalHorizonOutcomeResponse> horizonOutcomes
    ) {
        return SignalJournalResponse.builder()
                .id(journal.getId())
                .ticker(journal.getTicker())
                .actionType(journal.getActionType())
                .actionLabel(journal.getActionLabel())
                .scoreDate(journal.getScoreDate())
                .herdScore(journal.getHerdScore())
                .herdStage(journal.getHerdStage())
                .signal(operationalAction)
                .signalLabel("State S1 관찰")
                .actionRatio(operationalActionRatio)
                .signalDurationDays(null)
                .stageDurationDays(journal.getStageDurationDays())
                .price(journal.getPrice())
                .quantity(journal.getQuantity())
                .amount(journal.getAmount())
                .profitPct(journal.getProfitPct())
                .observationDate(observationDate)
                .referencePriceDate(referencePriceDate)
                .referencePrice(referencePrice)
                .horizonOutcomes(horizonOutcomes)
                .memo(journal.getMemo())
                .recordedAt(journal.getRecordedAt())
                .createdAt(journal.getCreatedAt())
                .build();
    }
}
