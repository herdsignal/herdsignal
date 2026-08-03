package com.herdsignal.service.decision;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** SEC 원문 검수 원장에서 방향 권한이 없는 atomic fact만 읽는다. */
@Slf4j
@Component
public class CsvPitGuidanceEvidenceProvider implements PitGuidanceEvidenceProvider {
    static final String SOURCE_VERSION = "HERD_SEC_GUIDANCE_ATOMIC_BINDINGS_V2";
    private static final String FACT_AUTHORITY = "SOURCE_REVIEWED_FACT_ONLY";

    private final Map<String, List<GuidanceEvidenceFactSnapshot>> byTicker;

    @Autowired
    public CsvPitGuidanceEvidenceProvider(
            @Value("${herdsignal.evidence.guidance-bindings-path:../data/reports/sec_guidance_atomic_bindings_v2.csv}")
            String configuredPath
    ) {
        this(resolvePath(configuredPath));
    }

    CsvPitGuidanceEvidenceProvider(Path path) {
        this.byTicker = load(path);
    }

    @Override
    public List<GuidanceEvidenceFactSnapshot> latestAccessionAsOf(
            String ticker,
            LocalDate observationDate
    ) {
        if (ticker == null || ticker.isBlank() || observationDate == null) return List.of();
        List<GuidanceEvidenceFactSnapshot> rows = byTicker.get(
                ticker.trim().toUpperCase(Locale.ROOT));
        if (rows == null) return List.of();
        GuidanceEvidenceFactSnapshot latest = null;
        for (GuidanceEvidenceFactSnapshot row : rows) {
            if (!row.acceptedAt().toLocalDate().isAfter(observationDate)) latest = row;
            else break;
        }
        if (latest == null) return List.of();
        String accession = latest.accessionNumber();
        return rows.stream()
                .filter(row -> row.accessionNumber().equals(accession))
                .sorted(Comparator.comparing(GuidanceEvidenceFactSnapshot::bindingId))
                .toList();
    }

    private Map<String, List<GuidanceEvidenceFactSnapshot>> load(Path path) {
        if (!Files.isRegularFile(path)) {
            log.warn("[operating-review] SEC 가이던스 원장 없음: {}", path.toAbsolutePath());
            return Map.of();
        }
        Map<String, List<GuidanceEvidenceFactSnapshot>> result = new HashMap<>();
        try (var lines = Files.lines(path)) {
            var iterator = lines.iterator();
            if (!iterator.hasNext()) return Map.of();
            Map<String, Integer> columns = columns(EvidenceCsvSupport.parseLine(iterator.next()));
            String sourceVersion = SOURCE_VERSION + ":" + EvidenceCsvSupport.sha256(path);
            while (iterator.hasNext()) {
                List<String> row = EvidenceCsvSupport.parseLine(iterator.next());
                if (!FACT_AUTHORITY.equals(text(row, columns, "atomic_binding_authority"))
                        || bool(row, columns, "direction_authority")
                        || bool(row, columns, "veto_authority")) {
                    continue;
                }
                GuidanceEvidenceFactSnapshot snapshot = snapshot(row, columns, sourceVersion);
                result.computeIfAbsent(snapshot.ticker(), ignored -> new ArrayList<>()).add(snapshot);
            }
        } catch (RuntimeException | IOException error) {
            log.error("[operating-review] SEC 가이던스 원장 파싱 실패: {}", path, error);
            return Map.of();
        }
        result.values().forEach(rows -> rows.sort(
                Comparator.comparing(GuidanceEvidenceFactSnapshot::acceptedAt)
                        .thenComparing(GuidanceEvidenceFactSnapshot::bindingId)));
        return Map.copyOf(result);
    }

    private GuidanceEvidenceFactSnapshot snapshot(
            List<String> row,
            Map<String, Integer> columns,
            String sourceVersion
    ) {
        return new GuidanceEvidenceFactSnapshot(
                text(row, columns, "binding_id"),
                text(row, columns, "ticker").toUpperCase(Locale.ROOT),
                text(row, columns, "cik"),
                text(row, columns, "accession_number"),
                OffsetDateTime.parse(text(row, columns, "accepted_at")),
                text(row, columns, "source_url"),
                text(row, columns, "source_sha256"),
                text(row, columns, "source_kind"),
                text(row, columns, "metric"),
                text(row, columns, "fiscal_period"),
                text(row, columns, "accounting_basis"),
                text(row, columns, "metric_subtype"),
                text(row, columns, "unit"),
                decimal(row, columns, "lower_bound"),
                decimal(row, columns, "upper_bound"),
                decimal(row, columns, "midpoint"),
                sourceVersion
        );
    }

    private Map<String, Integer> columns(List<String> header) {
        Map<String, Integer> result = new HashMap<>();
        for (int index = 0; index < header.size(); index++) result.put(header.get(index), index);
        List<String> required = List.of(
                "binding_id", "ticker", "cik", "accession_number", "accepted_at",
                "source_url", "source_sha256", "source_kind", "metric", "fiscal_period",
                "accounting_basis", "metric_subtype", "unit", "lower_bound", "upper_bound",
                "midpoint", "atomic_binding_authority", "direction_authority", "veto_authority");
        if (!result.keySet().containsAll(required)) {
            throw new IllegalArgumentException("SEC guidance CSV schema mismatch");
        }
        return result;
    }

    private String text(List<String> row, Map<String, Integer> columns, String name) {
        int index = columns.get(name);
        return index < row.size() ? row.get(index).trim() : "";
    }

    private BigDecimal decimal(List<String> row, Map<String, Integer> columns, String name) {
        String value = text(row, columns, name);
        return value.isBlank() ? null : new BigDecimal(value);
    }

    private boolean bool(List<String> row, Map<String, Integer> columns, String name) {
        return Boolean.parseBoolean(text(row, columns, name));
    }

    private static Path resolvePath(String configuredPath) {
        Path configured = Path.of(configuredPath).normalize();
        if (Files.isRegularFile(configured)) return configured;
        Path fromRoot = Path.of("data/reports/sec_guidance_atomic_bindings_v2.csv");
        if (Files.isRegularFile(fromRoot)) return fromRoot;
        return configured;
    }
}
