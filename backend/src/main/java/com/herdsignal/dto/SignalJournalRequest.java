package com.herdsignal.dto;

import lombok.Getter;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * HERD 판단 기록 저장 요청.
 */
@Getter
@NoArgsConstructor
public class SignalJournalRequest {

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
}
