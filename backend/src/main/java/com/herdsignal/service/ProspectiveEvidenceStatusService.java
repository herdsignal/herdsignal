package com.herdsignal.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.dto.ProspectiveEvidenceStatusResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;

/** 전향 관찰 감사 파일이 행동 권한 없이 유효할 때만 상태를 공개한다. */
@Service
public class ProspectiveEvidenceStatusService {

    private static final String SCHEMA = "HERD_PROSPECTIVE_EVIDENCE_AUDIT_V1";
    private static final String HOLD = "HOLD";

    private final ObjectMapper objectMapper;
    private final Path reportPath;

    public ProspectiveEvidenceStatusService(
            ObjectMapper objectMapper,
            @Value("${herdsignal.prospective.audit-path:"
                    + "../data/runtime/reports/prospective-evidence-latest.json}")
            String reportPath
    ) {
        this.objectMapper = objectMapper;
        this.reportPath = Path.of(reportPath).toAbsolutePath().normalize();
    }

    public ProspectiveEvidenceStatusResponse getStatus() {
        try {
            if (!Files.isRegularFile(reportPath)) return unavailable("REPORT_UNAVAILABLE");
            JsonNode root = objectMapper.readTree(Files.readAllBytes(reportPath));
            validate(root);
            return new ProspectiveEvidenceStatusResponse(
                    "COLLECTING",
                    true,
                    root.path("observationArchives").asInt(),
                    date(root, "firstObservationDate"),
                    date(root, "latestObservationDate"),
                    root.path("observationRecords").asInt(),
                    root.path("maturedOutcomes").asInt(),
                    root.path("pendingOutcomes").asInt(),
                    HOLD,
                    BigDecimal.ZERO
            );
        } catch (IOException | IllegalArgumentException exception) {
            return unavailable("REPORT_INVALID");
        }
    }

    private void validate(JsonNode root) {
        if (
                root == null
                || !root.isObject()
                || !SCHEMA.equals(root.path("schemaVersion").asText())
                || !"PASS".equals(root.path("status").asText())
                || !HOLD.equals(root.path("operationalAction").asText())
                || !root.path("operationalActionRatio").isNumber()
                || root.path("operationalActionRatio").decimalValue()
                        .compareTo(BigDecimal.ZERO) != 0
        ) {
            throw new IllegalArgumentException("전향 관찰 감사 계약이 유효하지 않습니다.");
        }
    }

    private LocalDate date(JsonNode root, String field) {
        String value = root.path(field).asText(null);
        return value == null || value.isBlank() ? null : LocalDate.parse(value);
    }

    private ProspectiveEvidenceStatusResponse unavailable(String status) {
        return new ProspectiveEvidenceStatusResponse(
                status, false, 0, null, null, 0, 0, 0, HOLD, BigDecimal.ZERO
        );
    }
}
