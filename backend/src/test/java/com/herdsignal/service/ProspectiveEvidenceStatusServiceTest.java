package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;

class ProspectiveEvidenceStatusServiceTest {

    @TempDir
    Path tempDir;

    @Test
    void exposesOnlyAnAuditedActionlessLedger() throws Exception {
        Path report = tempDir.resolve("audit.json");
        Files.writeString(report, validReport());

        var result = new ProspectiveEvidenceStatusService(
                new ObjectMapper(), report.toString()).getStatus();

        assertThat(result.status()).isEqualTo("COLLECTING");
        assertThat(result.auditPassed()).isTrue();
        assertThat(result.observationArchives()).isEqualTo(1);
        assertThat(result.observationRecords()).isEqualTo(440);
        assertThat(result.pendingOutcomes()).isEqualTo(1320);
        assertThat(result.operationalAction()).isEqualTo("HOLD");
        assertThat(result.operationalActionRatio()).isZero();
    }

    @Test
    void nonZeroActionRatioFailsClosed() throws Exception {
        Path report = tempDir.resolve("unsafe.json");
        Files.writeString(report, validReport().replace(
                "\"operationalActionRatio\": 0.0",
                "\"operationalActionRatio\": 0.05"
        ));

        var result = new ProspectiveEvidenceStatusService(
                new ObjectMapper(), report.toString()).getStatus();

        assertThat(result.status()).isEqualTo("REPORT_INVALID");
        assertThat(result.auditPassed()).isFalse();
        assertThat(result.operationalAction()).isEqualTo("HOLD");
        assertThat(result.operationalActionRatio()).isZero();
    }

    private String validReport() {
        return """
                {
                  "schemaVersion": "HERD_PROSPECTIVE_EVIDENCE_AUDIT_V1",
                  "status": "PASS",
                  "observationArchives": 1,
                  "firstObservationDate": "2026-07-24",
                  "latestObservationDate": "2026-07-24",
                  "observationRecords": 440,
                  "maturedOutcomes": 0,
                  "pendingOutcomes": 1320,
                  "operationalAction": "HOLD",
                  "operationalActionRatio": 0.0
                }
                """;
    }
}
