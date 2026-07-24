package com.herdsignal.dto;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
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

    @NotBlank(message = "티커는 필수입니다")
    @Pattern(regexp = "(?i)^[A-Z0-9.-]{1,10}$", message = "티커 형식이 올바르지 않습니다")
    private String ticker;
    @NotBlank(message = "판단 유형은 필수입니다")
    @Pattern(regexp = "(?i)BUY|HOLD|SELL", message = "판단 유형은 BUY/HOLD/SELL 중 하나여야 합니다")
    private String actionType;
    @Size(max = 50, message = "행동 문구는 50자 이하여야 합니다")
    private String actionLabel;
    private LocalDate scoreDate;
    private BigDecimal herdScore;
    @Size(max = 20, message = "HERD 단계는 20자 이하여야 합니다")
    private String herdStage;
    @Size(max = 20, message = "신호는 20자 이하여야 합니다")
    private String signal;
    @Size(max = 100, message = "신호 설명은 100자 이하여야 합니다")
    private String signalLabel;
    @DecimalMin(value = "0.0", message = "행동 비율은 0% 이상이어야 합니다")
    @DecimalMax(value = "1.0", message = "행동 비율은 100% 이하여야 합니다")
    private BigDecimal actionRatio;
    private Long signalDurationDays;
    private Long stageDurationDays;
    private BigDecimal price;
    private BigDecimal quantity;
    private BigDecimal amount;
    private BigDecimal profitPct;
    @Size(max = 1000, message = "메모는 1000자 이하여야 합니다")
    private String memo;
    private LocalDateTime recordedAt;
}
