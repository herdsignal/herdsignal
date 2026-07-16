package com.herdsignal.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.herdsignal.dto.ModelValidationReportResponse;
import com.herdsignal.exception.ModelReportUnavailableException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.FileTime;
import java.util.ArrayList;
import java.util.List;

/** Python 검증 산출물을 HERD Lab용 안정적인 API 계약으로 변환한다. */
@Service
public class ModelValidationReportService {

    private final ObjectMapper objectMapper;
    private final Path reportPath;
    private FileTime cachedModifiedAt;
    private ModelValidationReportResponse cachedReport;

    public ModelValidationReportService(
            ObjectMapper objectMapper,
            @Value("${herdsignal.validation-report-path:../data/reports/validation_v2/validation_v2.json}")
            String reportPath
    ) {
        this.objectMapper = objectMapper;
        this.reportPath = Path.of(reportPath).toAbsolutePath().normalize();
    }

    public synchronized ModelValidationReportResponse getReport() {
        try {
            if (!Files.isRegularFile(reportPath)) {
                throw new ModelReportUnavailableException("모델 검증 리포트가 아직 생성되지 않았습니다.");
            }
            FileTime modifiedAt = Files.getLastModifiedTime(reportPath);
            if (cachedReport != null && modifiedAt.equals(cachedModifiedAt)) {
                return cachedReport;
            }

            JsonNode root = objectMapper.readTree(reportPath.toFile());
            ModelValidationReportResponse report = mapReport(root);
            cachedModifiedAt = modifiedAt;
            cachedReport = report;
            return report;
        } catch (ModelReportUnavailableException exception) {
            throw exception;
        } catch (IOException | IllegalArgumentException exception) {
            throw new ModelReportUnavailableException("모델 검증 리포트를 읽을 수 없습니다.", exception);
        }
    }

    private ModelValidationReportResponse mapReport(JsonNode root) {
        JsonNode metadata = required(root, "metadata");
        JsonNode run = required(metadata, "validation_run");
        JsonNode stability = required(metadata, "parameter_stability");
        JsonNode transition = required(stability, "transition_stability");
        JsonNode overfitting = required(metadata, "overfitting");
        JsonNode cscv = required(overfitting, "cscv");
        JsonNode dsr = required(overfitting, "deflated_sharpe");
        JsonNode gate = required(metadata, "adoption_gate");
        JsonNode actionOutcomes = metadata.path("action_outcomes").path("horizons");

        List<ModelValidationReportResponse.TickerResult> tickers = new ArrayList<>();
        for (JsonNode row : required(root, "rows")) {
            tickers.add(new ModelValidationReportResponse.TickerResult(
                    text(row, "ticker"), text(row, "start"), text(row, "end"),
                    number(row, "buyhold_return"), number(row, "v61_return"),
                    number(row, "v61_capture"), number(row, "v61_mdd_improvement"),
                    integer(row, "v61_actions")
            ));
        }

        return new ModelValidationReportResponse(
                text(metadata, "generated_at"), text(metadata, "model"), text(metadata, "universe"),
                new ModelValidationReportResponse.ValidationRun(
                        text(run, "status"), integer(run, "requested_tickers"),
                        integer(run, "completed_tickers"), numberValue(run, "coverage"),
                        integer(run, "embargo_days")
                ),
                summary(required(root, "summary")),
                summary(required(metadata, "walk_forward_summary")),
                new ModelValidationReportResponse.ParameterStability(
                        integer(stability, "samples"), number(transition, "same_parameter_rate"),
                        bool(stability, "single_parameter_spike"), text(stability, "recommendation")
                ),
                new ModelValidationReportResponse.Overfitting(
                        integer(overfitting, "parameters_tested"), number(cscv, "pbo"),
                        text(cscv, "status"), number(dsr, "probability"), text(dsr, "status")
                ),
                new ModelValidationReportResponse.AdoptionGate(
                        text(gate, "policy_version"), text(gate, "status"),
                        bool(gate, "eligible_for_human_review"),
                        bool(gate, "automatic_production_promotion"),
                        strings(required(gate, "failed_criteria"))
                ),
                mapActionOutcomes(actionOutcomes),
                required(metadata, "score_parity").path("passed").asBoolean(false),
                text(required(metadata, "survivorship_coverage"), "status"),
                List.copyOf(tickers)
        );
    }

    private List<ModelValidationReportResponse.ActionOutcome> mapActionOutcomes(JsonNode horizons) {
        List<ModelValidationReportResponse.ActionOutcome> outcomes = new ArrayList<>();
        for (String horizon : List.of("1m", "3m", "6m")) {
            JsonNode node = horizons.path(horizon);
            outcomes.add(new ModelValidationReportResponse.ActionOutcome(
                    horizon,
                    integer(node, "samples"),
                    number(node, "hit_rate"),
                    number(node, "forward_return_mean"),
                    number(node, "drawdown_mean"),
                    number(node, "counterfactual_delta_mean")
            ));
        }
        return List.copyOf(outcomes);
    }

    private ModelValidationReportResponse.PerformanceSummary summary(JsonNode node) {
        return new ModelValidationReportResponse.PerformanceSummary(
                integer(node, "ticker_count"), number(node, "capture_median"),
                number(node, "mdd_improvement_median"), number(node, "improvement_rate"),
                text(node, "worst_ticker")
        );
    }

    private static JsonNode required(JsonNode node, String field) {
        JsonNode value = node.path(field);
        if (value.isMissingNode() || value.isNull()) {
            throw new IllegalArgumentException("필수 필드 누락: " + field);
        }
        return value;
    }

    private static String text(JsonNode node, String field) {
        JsonNode value = node.path(field);
        return value.isMissingNode() || value.isNull() ? null : value.asText();
    }

    private static int integer(JsonNode node, String field) {
        return node.path(field).asInt(0);
    }

    private static boolean bool(JsonNode node, String field) {
        return node.path(field).asBoolean(false);
    }

    private static Double number(JsonNode node, String field) {
        JsonNode value = node.path(field);
        return value.isNumber() ? value.doubleValue() : null;
    }

    private static double numberValue(JsonNode node, String field) {
        Double value = number(node, field);
        return value == null ? 0.0 : value;
    }

    private static List<String> strings(JsonNode node) {
        List<String> values = new ArrayList<>();
        node.forEach(value -> values.add(value.asText()));
        return List.copyOf(values);
    }
}
