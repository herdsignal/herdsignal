package com.herdsignal.service.decision;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class CsvPitGuidanceEvidenceProviderTest {
    private static final String HEADER = "binding_id,ticker,cik,accession_number,accepted_at,"
            + "document_name,source_url,source_sha256,source_kind,block_path,source_structure,"
            + "range_offset,metric,fiscal_period,accounting_basis,metric_subtype,unit,"
            + "lower_bound,upper_bound,midpoint,review_id,reviewer,reviewed_at,review_ledger,"
            + "review_ledger_sha256,semantic_locator_collision,pair_eligible,"
            + "atomic_binding_authority,direction_authority,veto_authority\n";

    @TempDir
    Path tempDir;

    @Test
    void returnsOnlyLatestPublicAccessionAndKeepsDirectionAuthorityOff() throws Exception {
        Path csv = tempDir.resolve("guidance.csv");
        Files.writeString(csv, HEADER
                + row("old", "0001", "2025-02-01T12:00:00Z", "REVENUE", "100", "110", false)
                + row("new-a", "0002", "2026-02-01T12:00:00Z", "REVENUE", "120", "130", false)
                + row("new-b", "0002", "2026-02-01T12:00:00Z", "EPS", "2.1", "2.3", false)
                + row("forbidden", "0003", "2026-03-01T12:00:00Z", "EPS", "3", "4", true));

        CsvPitGuidanceEvidenceProvider provider = new CsvPitGuidanceEvidenceProvider(csv);
        List<GuidanceEvidenceFactSnapshot> before = provider.latestAccessionAsOf(
                "nvda", LocalDate.of(2025, 12, 31));
        List<GuidanceEvidenceFactSnapshot> latest = provider.latestAccessionAsOf(
                "NVDA", LocalDate.of(2026, 4, 1));

        assertThat(before).extracting(GuidanceEvidenceFactSnapshot::bindingId)
                .containsExactly("old");
        assertThat(latest).extracting(GuidanceEvidenceFactSnapshot::bindingId)
                .containsExactly("new-a", "new-b");
        assertThat(latest).allMatch(row -> row.accessionNumber().equals("0002"));
        assertThat(latest.get(0).sourceVersion())
                .matches("HERD_SEC_GUIDANCE_ATOMIC_BINDINGS_V2:[0-9a-f]{64}");
    }

    private String row(
            String id,
            String accession,
            String acceptedAt,
            String metric,
            String lower,
            String upper,
            boolean directionAuthority
    ) {
        return String.join(",", id, "NVDA", "0001045810", accession, acceptedAt,
                "ex99.htm", "https://www.sec.gov/example", "abc123", "HTML_TABLE",
                "/table[1]", "TABLE_ROW", "1", metric, "FY2026", "NON_GAAP",
                "NOT_APPLICABLE", "USD", lower, upper, lower, "review", "reviewer",
                "2026-07-01", "ledger.csv", "ledgerhash", "False", "True",
                "SOURCE_REVIEWED_FACT_ONLY", Boolean.toString(directionAuthority), "False") + "\n";
    }
}
