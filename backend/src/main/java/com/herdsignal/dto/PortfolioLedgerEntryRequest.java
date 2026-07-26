package com.herdsignal.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;

@Getter
@NoArgsConstructor
public class PortfolioLedgerEntryRequest {

    @NotBlank
    private String entryType;

    private String ticker;

    @NotNull
    private LocalDate occurredOn;

    private BigDecimal quantity;
    private BigDecimal unitPrice;
    private BigDecimal amount;
    private BigDecimal fee;
    private String note;
}
