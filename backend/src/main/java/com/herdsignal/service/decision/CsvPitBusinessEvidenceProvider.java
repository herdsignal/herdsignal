package com.herdsignal.service.decision;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;

/** 잠긴 SEC PIT 연구 산출물을 읽기 전용 런타임 근거로 제공한다. */
@Slf4j
@Component
public class CsvPitBusinessEvidenceProvider implements PitBusinessEvidenceProvider {
    static final String SOURCE_VERSION = "HERD_SEC_PIT_BUSINESS_FACTS_V1";

    private final Map<String, List<BusinessEvidenceSnapshot>> byTicker;

    @Autowired
    public CsvPitBusinessEvidenceProvider(
            @Value("${herdsignal.evidence.business-state-path:../data/reports/business_state_features_v2.csv}")
            String configuredPath
    ) {
        this(resolvePath(configuredPath));
    }

    CsvPitBusinessEvidenceProvider(Path path) {
        this.byTicker = load(path);
    }

    @Override
    public Optional<BusinessEvidenceSnapshot> latestAsOf(String ticker, LocalDate observationDate) {
        if (ticker == null || ticker.isBlank() || observationDate == null) {
            return Optional.empty();
        }
        List<BusinessEvidenceSnapshot> rows = byTicker.get(ticker.trim().toUpperCase(Locale.ROOT));
        if (rows == null) return Optional.empty();
        for (int index = rows.size() - 1; index >= 0; index--) {
            BusinessEvidenceSnapshot row = rows.get(index);
            if (!row.featureMonthEnd().isAfter(observationDate)
                    && (row.latestFactAcceptedAt() == null
                    || !row.latestFactAcceptedAt().toLocalDate().isAfter(observationDate))) {
                return Optional.of(row);
            }
        }
        return Optional.empty();
    }

    private Map<String, List<BusinessEvidenceSnapshot>> load(Path path) {
        if (!Files.isRegularFile(path)) {
            log.warn("[operating-review] SEC PIT 기업 사실 파일 없음: {}", path.toAbsolutePath());
            return Map.of();
        }
        Map<String, List<BusinessEvidenceSnapshot>> result = new HashMap<>();
        try (var lines = Files.lines(path)) {
            String sourceVersion = SOURCE_VERSION + ":" + sha256(path);
            var iterator = lines.iterator();
            if (!iterator.hasNext()) return Map.of();
            List<String> header = parseCsvLine(iterator.next());
            Map<String, Integer> columns = columns(header);
            while (iterator.hasNext()) {
                List<String> row = parseCsvLine(iterator.next());
                BusinessEvidenceSnapshot snapshot = snapshot(row, columns, sourceVersion);
                result.computeIfAbsent(snapshot.ticker(), ignored -> new ArrayList<>()).add(snapshot);
            }
        } catch (RuntimeException | IOException error) {
            log.error("[operating-review] SEC PIT 기업 사실 파일 파싱 실패: {}", path, error);
            return Map.of();
        }
        result.values().forEach(rows -> rows.sort(
                Comparator.comparing(BusinessEvidenceSnapshot::featureMonthEnd)));
        return Map.copyOf(result);
    }

    private BusinessEvidenceSnapshot snapshot(
            List<String> row,
            Map<String, Integer> columns,
            String sourceVersion
    ) {
        return new BusinessEvidenceSnapshot(
                text(row, columns, "ticker").toUpperCase(Locale.ROOT),
                text(row, columns, "cik"),
                LocalDate.parse(text(row, columns, "month_end")),
                text(row, columns, "corpus_status"),
                offsetDateTime(row, columns, "latest_fact_accepted_at"),
                text(row, columns, "entity_type"),
                sourceVersion,
                decimal(row, columns, "revenue_yoy"),
                decimal(row, columns, "net_margin"),
                decimal(row, columns, "net_margin_yoy_change"),
                decimal(row, columns, "operating_cash_flow_yoy"),
                decimal(row, columns, "operating_cash_flow_value"),
                decimal(row, columns, "liabilities_to_assets"),
                decimal(row, columns, "liabilities_to_assets_yoy_change")
        );
    }

    private Map<String, Integer> columns(List<String> header) {
        Map<String, Integer> result = new HashMap<>();
        for (int index = 0; index < header.size(); index++) result.put(header.get(index), index);
        List<String> required = List.of(
                "ticker", "cik", "month_end", "corpus_status", "latest_fact_accepted_at",
                "entity_type", "revenue_yoy", "net_margin", "net_margin_yoy_change",
                "operating_cash_flow_yoy", "operating_cash_flow_value",
                "liabilities_to_assets", "liabilities_to_assets_yoy_change");
        if (!result.keySet().containsAll(required)) {
            throw new IllegalArgumentException("SEC PIT business CSV schema mismatch");
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

    private OffsetDateTime offsetDateTime(List<String> row, Map<String, Integer> columns, String name) {
        String value = text(row, columns, name);
        return value.isBlank() ? null : OffsetDateTime.parse(value);
    }

    static List<String> parseCsvLine(String line) {
        List<String> values = new ArrayList<>();
        StringBuilder value = new StringBuilder();
        boolean quoted = false;
        for (int index = 0; index < line.length(); index++) {
            char current = line.charAt(index);
            if (current == '"') {
                if (quoted && index + 1 < line.length() && line.charAt(index + 1) == '"') {
                    value.append('"');
                    index++;
                } else {
                    quoted = !quoted;
                }
            } else if (current == ',' && !quoted) {
                values.add(value.toString());
                value.setLength(0);
            } else {
                value.append(current);
            }
        }
        values.add(value.toString());
        if (quoted) throw new IllegalArgumentException("unterminated quoted CSV field");
        return values;
    }

    private String sha256(Path path) throws IOException {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (var input = Files.newInputStream(path)) {
                byte[] buffer = new byte[8192];
                int read;
                while ((read = input.read(buffer)) >= 0) digest.update(buffer, 0, read);
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256 unavailable", impossible);
        }
    }

    private static Path resolvePath(String configuredPath) {
        Path configured = Path.of(configuredPath).normalize();
        if (Files.isRegularFile(configured)) return configured;
        Path fromRoot = Path.of("data/reports/business_state_features_v2.csv");
        if (Files.isRegularFile(fromRoot)) return fromRoot;
        return configured;
    }
}
