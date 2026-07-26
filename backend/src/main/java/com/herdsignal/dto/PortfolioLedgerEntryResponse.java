package com.herdsignal.dto;

import com.herdsignal.domain.PortfolioLedgerEntry;
import com.herdsignal.domain.PortfolioLedgerEntryType;
import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Getter
@Builder
public class PortfolioLedgerEntryResponse {

    private Long id;
    private String entryType;
    private String ticker;
    private LocalDate occurredOn;
    private BigDecimal quantity;
    private BigDecimal unitPrice;
    private BigDecimal grossAmount;
    private BigDecimal feeAmount;
    private BigDecimal cashEffect;
    private String currency;
    private String source;
    private String note;
    private LocalDateTime createdAt;

    public static PortfolioLedgerEntryResponse from(PortfolioLedgerEntry entry) {
        return PortfolioLedgerEntryResponse.builder()
                .id(entry.getId())
                .entryType(entry.getEntryType().name())
                .ticker(entry.getTicker())
                .occurredOn(entry.getOccurredOn())
                .quantity(entry.getQuantity())
                .unitPrice(entry.getUnitPrice())
                .grossAmount(entry.getGrossAmount())
                .feeAmount(entry.getFeeAmount())
                .cashEffect(cashEffect(entry))
                .currency(entry.getCurrency())
                .source(entry.getSource())
                .note(entry.getNote())
                .createdAt(entry.getCreatedAt())
                .build();
    }

    private static BigDecimal cashEffect(PortfolioLedgerEntry entry) {
        BigDecimal gross = entry.getGrossAmount();
        BigDecimal fee = entry.getFeeAmount();
        PortfolioLedgerEntryType type = entry.getEntryType();
        return switch (type) {
            case BUY -> gross.add(fee).negate();
            case SELL -> gross.subtract(fee);
            case DEPOSIT, DIVIDEND -> gross;
            case WITHDRAWAL, FEE -> gross.negate();
        };
    }
}
