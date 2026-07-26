package com.herdsignal.service;

import com.herdsignal.domain.PortfolioLedgerEntry;
import com.herdsignal.domain.PortfolioLedgerEntryType;
import com.herdsignal.dto.PortfolioLedgerEntryRequest;
import com.herdsignal.dto.PortfolioLedgerEntryResponse;
import com.herdsignal.exception.ResourceNotFoundException;
import com.herdsignal.repository.PortfolioLedgerEntryRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Locale;

@Service
@RequiredArgsConstructor
public class PortfolioLedgerService {

    private static final BigDecimal ZERO = BigDecimal.ZERO.setScale(2);

    private final PortfolioLedgerEntryRepository repository;
    private final TickerSymbolPolicy tickerSymbolPolicy;

    @Transactional(readOnly = true)
    public List<PortfolioLedgerEntryResponse> getEntries(String userId, String ticker) {
        List<PortfolioLedgerEntry> entries = ticker == null || ticker.isBlank()
                ? repository.findByUserIdOrderByOccurredOnDescIdDesc(userId)
                : repository.findByUserIdAndTickerOrderByOccurredOnDescIdDesc(
                        userId,
                        tickerSymbolPolicy.normalize(ticker)
                );
        return entries.stream().map(PortfolioLedgerEntryResponse::from).toList();
    }

    @Transactional
    public PortfolioLedgerEntryResponse create(
            String userId,
            PortfolioLedgerEntryRequest request
    ) {
        PortfolioLedgerEntryType type = parseType(request.getEntryType());
        validateDate(request.getOccurredOn());
        String ticker = normalizedTicker(type, request.getTicker());
        BigDecimal fee = nonNegative(request.getFee(), "수수료").setScale(
                2,
                RoundingMode.HALF_UP
        );

        BigDecimal quantity = null;
        BigDecimal unitPrice = null;
        BigDecimal grossAmount;
        if (type == PortfolioLedgerEntryType.BUY || type == PortfolioLedgerEntryType.SELL) {
            quantity = positive(request.getQuantity(), "수량").setScale(6, RoundingMode.HALF_UP);
            unitPrice = positive(request.getUnitPrice(), "단가").setScale(6, RoundingMode.HALF_UP);
            grossAmount = quantity.multiply(unitPrice).setScale(2, RoundingMode.HALF_UP);
            if (type == PortfolioLedgerEntryType.SELL && fee.compareTo(grossAmount) > 0) {
                throw new IllegalArgumentException("매도 수수료는 거래 금액을 초과할 수 없습니다.");
            }
        } else {
            grossAmount = positive(request.getAmount(), "금액").setScale(2, RoundingMode.HALF_UP);
            if (fee.compareTo(BigDecimal.ZERO) > 0) {
                throw new IllegalArgumentException("현금성 항목의 수수료는 별도 FEE로 기록해주세요.");
            }
        }

        PortfolioLedgerEntry saved = repository.save(PortfolioLedgerEntry.builder()
                .userId(userId)
                .entryType(type)
                .ticker(ticker)
                .occurredOn(request.getOccurredOn())
                .quantity(quantity)
                .unitPrice(unitPrice)
                .grossAmount(grossAmount)
                .feeAmount(fee)
                .currency("USD")
                .source("MANUAL")
                .note(cleanNote(request.getNote()))
                .createdAt(LocalDateTime.now())
                .build());
        return PortfolioLedgerEntryResponse.from(saved);
    }

    @Transactional
    public void delete(String userId, Long id) {
        PortfolioLedgerEntry entry = repository.findByIdAndUserId(id, userId)
                .orElseThrow(() -> new ResourceNotFoundException("원장 항목을 찾을 수 없습니다."));
        repository.delete(entry);
    }

    private PortfolioLedgerEntryType parseType(String value) {
        try {
            return PortfolioLedgerEntryType.valueOf(value.trim().toUpperCase(Locale.ROOT));
        } catch (RuntimeException exception) {
            throw new IllegalArgumentException(
                    "원장 유형은 BUY/SELL/DEPOSIT/WITHDRAWAL/DIVIDEND/FEE 중 하나여야 합니다."
            );
        }
    }

    private String normalizedTicker(PortfolioLedgerEntryType type, String rawTicker) {
        boolean required = type == PortfolioLedgerEntryType.BUY
                || type == PortfolioLedgerEntryType.SELL
                || type == PortfolioLedgerEntryType.DIVIDEND;
        if (!required && (rawTicker == null || rawTicker.isBlank())) return null;
        if (
                (type == PortfolioLedgerEntryType.DEPOSIT
                        || type == PortfolioLedgerEntryType.WITHDRAWAL)
                && rawTicker != null
                && !rawTicker.isBlank()
        ) {
            throw new IllegalArgumentException("입출금 항목에는 종목을 지정할 수 없습니다.");
        }
        return tickerSymbolPolicy.normalize(rawTicker);
    }

    private void validateDate(LocalDate date) {
        if (date == null) throw new IllegalArgumentException("거래일은 필수입니다.");
        if (date.isAfter(LocalDate.now())) {
            throw new IllegalArgumentException("미래 날짜는 원장에 기록할 수 없습니다.");
        }
    }

    private BigDecimal positive(BigDecimal value, String label) {
        if (value == null || value.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException(label + "은 0보다 커야 합니다.");
        }
        return value;
    }

    private BigDecimal nonNegative(BigDecimal value, String label) {
        if (value == null) return ZERO;
        if (value.compareTo(BigDecimal.ZERO) < 0) {
            throw new IllegalArgumentException(label + "은 0 이상이어야 합니다.");
        }
        return value;
    }

    private String cleanNote(String value) {
        if (value == null || value.isBlank()) return null;
        String note = value.trim();
        if (note.length() > 200) {
            throw new IllegalArgumentException("메모는 200자 이하여야 합니다.");
        }
        return note;
    }
}
