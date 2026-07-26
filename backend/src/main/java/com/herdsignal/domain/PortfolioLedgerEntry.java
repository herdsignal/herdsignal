package com.herdsignal.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Entity
@Table(
        name = "portfolio_ledger_entries",
        indexes = {
                @Index(
                        name = "ix_portfolio_ledger_user_date",
                        columnList = "user_id, occurred_on, id"
                ),
                @Index(
                        name = "ix_portfolio_ledger_user_ticker_date",
                        columnList = "user_id, ticker, occurred_on"
                )
        }
)
@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PortfolioLedgerEntry {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false, length = 50)
    private String userId;

    @Enumerated(EnumType.STRING)
    @Column(name = "entry_type", nullable = false, length = 20)
    private PortfolioLedgerEntryType entryType;

    @Column(name = "ticker", length = 10)
    private String ticker;

    @Column(name = "occurred_on", nullable = false)
    private LocalDate occurredOn;

    @Column(name = "quantity", precision = 18, scale = 6)
    private BigDecimal quantity;

    @Column(name = "unit_price", precision = 16, scale = 6)
    private BigDecimal unitPrice;

    @Column(name = "gross_amount", nullable = false, precision = 18, scale = 2)
    private BigDecimal grossAmount;

    @Column(name = "fee_amount", nullable = false, precision = 16, scale = 2)
    private BigDecimal feeAmount;

    @Column(name = "currency", nullable = false, length = 3)
    private String currency;

    @Column(name = "source", nullable = false, length = 20)
    private String source;

    @Column(name = "note", length = 200)
    private String note;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;
}
