package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.dto.ModelValidationReportResponse;
import com.herdsignal.exception.ModelReportUnavailableException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ModelValidationReportServiceTest {

    @TempDir
    Path tempDir;

    @Test
    void mapsValidationReportAndReusesUnchangedFile() throws Exception {
        Path report = tempDir.resolve("validation.json");
        Files.writeString(report, """
                {
                  "metadata": {
                    "generated_at": "2026-07-14T00:00:00Z",
                    "model": "HERD_v6.1",
                    "universe": "2026.07",
                    "validation_run": {"status":"COMPLETE","requested_tickers":55,"completed_tickers":55,"coverage":1.0,"embargo_days":20},
                    "walk_forward_summary": {"ticker_count":440,"capture_median":99.1,"mdd_improvement_median":0.9,"improvement_rate":36.4,"worst_ticker":"META"},
                    "parameter_stability": {"samples":440,"transition_stability":{"same_parameter_rate":59.4},"single_parameter_spike":true,"recommendation":"USE_FIXED_PARAMETERS"},
                    "overfitting": {"parameters_tested":9,"cscv":{"pbo":0.0,"status":"ACCEPTABLE"},"deflated_sharpe":{"probability":0.0,"status":"FAIL"}},
                    "adoption_gate": {"policy_version":"2026.07-v1","status":"RESEARCH_VALIDATION","eligible_for_human_review":false,"automatic_production_promotion":false,"failed_criteria":["deflated_sharpe"]},
                    "action_outcomes": {"horizons":{"1m":{"samples":100,"hit_rate":61.0,"forward_return_mean":2.0,"drawdown_mean":-4.0,"counterfactual_delta_mean":0.3},"3m":{"samples":80,"hit_rate":64.0},"6m":{"samples":60,"hit_rate":68.0}}},
                    "score_parity": {"passed":true},
                    "survivorship_coverage": {"status":"SURVIVORSHIP_BIAS_REMAINS"}
                  },
                  "summary": {"ticker_count":55,"capture_median":64.1,"mdd_improvement_median":8.1,"improvement_rate":74.5,"worst_ticker":"BA"},
                  "rows": [{"ticker":"SPY","start":"2018-01-01","end":"2026-01-01","buyhold_return":300.0,"v61_return":200.0,"v61_capture":66.7,"v61_mdd_improvement":5.0,"v61_actions":20}],
                  "walk_forward": []
                }
                """);
        ModelValidationReportService service = new ModelValidationReportService(
                new ObjectMapper(), report.toString());

        ModelValidationReportResponse first = service.getReport();
        ModelValidationReportResponse second = service.getReport();

        assertThat(first.modelVersion()).isEqualTo("HERD_v6.1");
        assertThat(first.validationRun().coverage()).isEqualTo(1.0);
        assertThat(first.walkForward().samples()).isEqualTo(440);
        assertThat(first.adoptionGate().failedCriteria()).containsExactly("deflated_sharpe");
        assertThat(first.actionOutcomes()).hasSize(3);
        assertThat(first.actionOutcomes().get(0).samples()).isEqualTo(100);
        assertThat(first.tickers()).singleElement().extracting(
                ModelValidationReportResponse.TickerResult::ticker).isEqualTo("SPY");
        assertThat(second).isSameAs(first);
    }

    @Test
    void rejectsMissingReport() {
        ModelValidationReportService service = new ModelValidationReportService(
                new ObjectMapper(), tempDir.resolve("missing.json").toString());

        assertThatThrownBy(service::getReport)
                .isInstanceOf(ModelReportUnavailableException.class)
                .hasMessageContaining("아직 생성되지 않았습니다");
    }
}
