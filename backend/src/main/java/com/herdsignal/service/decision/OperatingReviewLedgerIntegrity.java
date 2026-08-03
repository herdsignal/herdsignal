package com.herdsignal.service.decision;

import com.herdsignal.domain.OperatingReviewSnapshot;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.HexFormat;

/** 판단 원문의 해시와 원장 핵심 열을 함께 검증한다. */
@Component
public class OperatingReviewLedgerIntegrity {
    public static final String VERSION = "OPERATING_REVIEW_LEDGER_V1";

    public String payloadHash(String payloadJson) {
        return sha256(payloadJson == null ? "" : payloadJson);
    }

    public String recordHash(OperatingReviewSnapshot row) {
        return sha256(String.join("\n",
                VERSION,
                text(row.getUserId()),
                text(row.getTicker()),
                text(row.getReviewedAt()),
                text(row.getObservationDate()),
                text(row.getReferencePriceDate()),
                decimal(row.getReferencePrice()),
                text(row.getDecisionCode()),
                Boolean.toString(row.isActionAuthorized()),
                decimal(row.getActionRatio()),
                text(row.getEvidenceSchemaVersion()),
                text(row.getDecisionModelVersion()),
                text(row.getPayloadSha256())
        ));
    }

    public Status verify(OperatingReviewSnapshot row) {
        if (row.getRecordSha256() == null || row.getRecordSha256().isBlank()) {
            return Status.LEGACY_UNVERIFIED;
        }
        boolean payloadMatches = constantTimeEquals(
                row.getPayloadSha256(), payloadHash(row.getPayloadJson()));
        boolean recordMatches = constantTimeEquals(
                row.getRecordSha256(), recordHash(row));
        return payloadMatches && recordMatches ? Status.VERIFIED : Status.MISMATCH;
    }

    private boolean constantTimeEquals(String left, String right) {
        if (left == null || right == null) return false;
        return MessageDigest.isEqual(
                left.getBytes(StandardCharsets.US_ASCII),
                right.getBytes(StandardCharsets.US_ASCII));
    }

    private String sha256(String value) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256을 사용할 수 없습니다.", exception);
        }
    }

    private String decimal(BigDecimal value) {
        return value == null ? "" : value.stripTrailingZeros().toPlainString();
    }

    private String text(Object value) {
        if (value == null) return "";
        if (value instanceof LocalDateTime dateTime) return dateTime.toString();
        if (value instanceof LocalDate date) return date.toString();
        return value.toString();
    }

    public enum Status {
        VERIFIED,
        LEGACY_UNVERIFIED,
        MISMATCH
    }
}
