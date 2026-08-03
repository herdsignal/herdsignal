package com.herdsignal.service.decision;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;

class CsvPitBusinessEvidenceProviderTest {
    private static final String HEADER = "ticker,cik,month_end,corpus_status,guard_state,"
            + "deterioration_flags,flag_count,latest_fact_accepted_at,reason,revenue_yoy,"
            + "net_margin,net_margin_yoy_change,operating_cash_flow_yoy,"
            + "operating_cash_flow_value,liabilities_to_assets,"
            + "liabilities_to_assets_yoy_change,entity_type\n";

    @TempDir
    Path tempDir;

    @Test
    void returnsOnlyFactsThatWerePublicByTheObservationDate() throws Exception {
        Path csv = tempDir.resolve("business.csv");
        Files.writeString(csv, HEADER
                + row("2026-03-31", "2026-02-20T20:00:00Z", "0.10")
                + row("2026-06-30", "2026-05-20T20:00:00Z", "0.20"));
        CsvPitBusinessEvidenceProvider provider = new CsvPitBusinessEvidenceProvider(csv);

        BusinessEvidenceSnapshot march = provider.latestAsOf(
                "nvda", LocalDate.of(2026, 4, 30)).orElseThrow();
        BusinessEvidenceSnapshot june = provider.latestAsOf(
                "NVDA", LocalDate.of(2026, 6, 30)).orElseThrow();

        assertThat(march.featureMonthEnd()).isEqualTo(LocalDate.of(2026, 3, 31));
        assertThat(march.revenueYoy()).isEqualByComparingTo("0.10");
        assertThat(june.featureMonthEnd()).isEqualTo(LocalDate.of(2026, 6, 30));
        assertThat(june.revenueYoy()).isEqualByComparingTo("0.20");
        assertThat(june.sourceVersion())
                .matches("HERD_SEC_PIT_BUSINESS_FACTS_V1:[0-9a-f]{64}");
        assertThat(provider.latestAsOf("NVDA", LocalDate.of(2026, 1, 1))).isEmpty();
    }

    @Test
    void parsesQuotedCsvFieldsWithoutShiftingFinancialColumns() throws Exception {
        Path csv = tempDir.resolve("quoted.csv");
        Files.writeString(csv, HEADER
                + "NVDA,0001045810,2026-06-30,PIT_FACTS_READY,PASS,\"MARGIN,NOTE\",1,"
                + "2026-05-20T20:00:00Z,,0.20,0.30,0.01,0.40,100,0.25,-0.02,GENERAL\n");

        BusinessEvidenceSnapshot row = new CsvPitBusinessEvidenceProvider(csv)
                .latestAsOf("NVDA", LocalDate.of(2026, 6, 30)).orElseThrow();

        assertThat(row.netMargin()).isEqualByComparingTo("0.30");
        assertThat(row.liabilitiesToAssets()).isEqualByComparingTo("0.25");
    }

    private String row(String monthEnd, String acceptedAt, String revenueYoy) {
        return "NVDA,0001045810," + monthEnd
                + ",PIT_FACTS_READY,PASS,,0," + acceptedAt + ",,"
                + revenueYoy + ",0.30,0.01,0.40,100,0.25,-0.02,GENERAL\n";
    }
}
