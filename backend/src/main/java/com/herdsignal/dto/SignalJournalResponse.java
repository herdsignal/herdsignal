package com.herdsignal.dto;

import com.herdsignal.domain.SignalJournal;
import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;

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
    private BigDecimal currentPrice;
    private BigDecimal outcomePct;
    private BigDecimal outcomeAmount;
    private Long outcomeDays;
    private String outcomeLabel;
    private String memo;
    private LocalDateTime recordedAt;
    private LocalDateTime createdAt;

    public static SignalJournalResponse from(SignalJournal journal) {
        return from(journal, null);
    }

    public static SignalJournalResponse from(SignalJournal journal, BigDecimal currentPrice) {
        Outcome outcome = calculateOutcome(journal, currentPrice);
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
                .currentPrice(currentPrice)
                .outcomePct(outcome.outcomePct())
                .outcomeAmount(outcome.outcomeAmount())
                .outcomeDays(outcome.outcomeDays())
                .outcomeLabel(outcome.outcomeLabel())
                .memo(journal.getMemo())
                .recordedAt(journal.getRecordedAt())
                .createdAt(journal.getCreatedAt())
                .build();
    }

    private static Outcome calculateOutcome(SignalJournal journal, BigDecimal currentPrice) {
        if (journal.getPrice() == null || currentPrice == null || journal.getPrice().compareTo(BigDecimal.ZERO) <= 0) {
            return new Outcome(null, null, outcomeDays(journal), null);
        }

        BigDecimal priceDeltaPct = currentPrice.subtract(journal.getPrice())
                .divide(journal.getPrice(), 8, RoundingMode.HALF_UP)
                .multiply(BigDecimal.valueOf(100))
                .setScale(4, RoundingMode.HALF_UP);

        BigDecimal outcomePct = priceDeltaPct;
        BigDecimal priceDiff = currentPrice.subtract(journal.getPrice());
        String label = "현재 변화";

        if ("SELL".equalsIgnoreCase(journal.getActionType())) {
            outcomePct = priceDeltaPct.negate();
            priceDiff = journal.getPrice().subtract(currentPrice);
            label = "익절 후 방어";
        } else if ("BUY".equalsIgnoreCase(journal.getActionType())) {
            label = "매수 후 변화";
        } else if ("HOLD".equalsIgnoreCase(journal.getActionType())) {
            label = "보류 후 변화";
        }

        BigDecimal amount = null;
        if (journal.getQuantity() != null) {
            amount = priceDiff.multiply(journal.getQuantity()).setScale(2, RoundingMode.HALF_UP);
        }

        return new Outcome(outcomePct, amount, outcomeDays(journal), label);
    }

    private static Long outcomeDays(SignalJournal journal) {
        LocalDateTime recordedAt = journal.getRecordedAt() != null ? journal.getRecordedAt() : journal.getCreatedAt();
        if (recordedAt == null) return null;
        return Math.max(0, ChronoUnit.DAYS.between(recordedAt.toLocalDate(), LocalDate.now()));
    }

    private record Outcome(
            BigDecimal outcomePct,
            BigDecimal outcomeAmount,
            Long outcomeDays,
            String outcomeLabel
    ) {
    }
}
