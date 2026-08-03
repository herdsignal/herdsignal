package com.herdsignal.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;

/** 채택 원장과 모든 참조 결과의 해시가 맞을 때만 증거 권한을 읽는다. */
@Service
public class EvidenceAdmissionAuthorityService {
    private static final String VERSION = "HERD_MODEL_EVIDENCE_ADMISSION_V1";

    private final ObjectMapper objectMapper;
    private final Path registryPath;

    public EvidenceAdmissionAuthorityService(
            ObjectMapper objectMapper,
            @Value("${herdsignal.evidence.admission-registry-path:../data/herd/model_evidence_admission_v1.json}")
            String registryPath
    ) {
        this.objectMapper = objectMapper;
        this.registryPath = Path.of(registryPath).toAbsolutePath().normalize();
    }

    public EvidenceAdmissionAuthority authority() {
        List<String> blockers = new ArrayList<>();
        try {
            if (!Files.isRegularFile(registryPath)) return invalid("REGISTRY_MISSING");
            JsonNode root = objectMapper.readTree(Files.readAllBytes(registryPath));
            if (!VERSION.equals(root.path("registry_version").asText())) {
                return invalid("REGISTRY_VERSION_INVALID");
            }
            Path projectRoot = registryPath.getParent().getParent().getParent();
            int profitTake = 0;
            int reentry = 0;
            int businessVeto = 0;
            for (JsonNode family : root.path("families")) {
                String path = family.path("result_path").asText();
                String expectedHash = family.path("result_sha256").asText();
                if (path.isBlank() || expectedHash.isBlank()
                        || !hashMatches(projectRoot.resolve(path).normalize(), expectedHash)) {
                    blockers.add("SOURCE_HASH_INVALID:" + family.path("id").asText("UNKNOWN"));
                }
                if (!family.path("admitted").asBoolean(false)) continue;
                if ("REJECTED".equals(family.path("decision").asText())) {
                    blockers.add("REJECTED_FAMILY_MARKED_ADMITTED:" + family.path("id").asText());
                    continue;
                }
                switch (family.path("role").asText()) {
                    case "PROFIT_TAKE_DIRECTION" -> profitTake++;
                    case "REENTRY_SUPPORT" -> reentry++;
                    case "BUSINESS_STATE_VETO" -> businessVeto++;
                    default -> {
                        // 방향 권한과 무관한 context family는 여기서 세지 않는다.
                    }
                }
            }
            JsonNode boundary = root.path("claim_boundary");
            boolean blindOpen = boundary.path("blind_holdout_access").asBoolean(false);
            boolean actionEnabled = boundary.path("next_stage_may_execute_trades").asBoolean(false);
            BigDecimal ratio = boundary.path("operational_action_ratio").decimalValue();
            verifySummary(root.path("admission_summary"), profitTake, reentry, businessVeto, blockers);
            if (blindOpen) blockers.add("BLIND_HOLDOUT_ALREADY_OPEN");
            if (actionEnabled || ratio.compareTo(BigDecimal.ZERO) != 0) {
                blockers.add("OPERATIONAL_AUTHORITY_NOT_ZERO");
            }
            boolean valid = blockers.stream().noneMatch(item ->
                    item.startsWith("SOURCE_HASH_INVALID")
                            || item.startsWith("REJECTED_FAMILY")
                            || item.startsWith("SUMMARY_MISMATCH")
                            || item.equals("OPERATIONAL_AUTHORITY_NOT_ZERO"));
            if (reentry == 0) blockers.add("ADD_DIRECTION_EVIDENCE_NOT_ADMITTED");
            if (businessVeto == 0) blockers.add("BUSINESS_VETO_EVIDENCE_NOT_ADMITTED");
            return new EvidenceAdmissionAuthority(
                    valid, profitTake, reentry, businessVeto, blindOpen,
                    actionEnabled, ratio, blockers);
        } catch (IOException | RuntimeException error) {
            return invalid("REGISTRY_INVALID");
        }
    }

    private void verifySummary(
            JsonNode summary,
            int profitTake,
            int reentry,
            int businessVeto,
            List<String> blockers
    ) {
        if (summary.path("direction_evidence_admitted").asInt(-1) != profitTake) {
            blockers.add("SUMMARY_MISMATCH:DIRECTION");
        }
        if (summary.path("reentry_support_admitted").asInt(-1) != reentry) {
            blockers.add("SUMMARY_MISMATCH:REENTRY");
        }
        if (summary.path("business_veto_admitted").asInt(-1) != businessVeto) {
            blockers.add("SUMMARY_MISMATCH:BUSINESS_VETO");
        }
    }

    private boolean hashMatches(Path path, String expected) throws IOException {
        if (!Files.isRegularFile(path)) return false;
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (var input = Files.newInputStream(path)) {
                byte[] buffer = new byte[8192];
                int read;
                while ((read = input.read(buffer)) >= 0) digest.update(buffer, 0, read);
            }
            return HexFormat.of().formatHex(digest.digest()).equalsIgnoreCase(expected);
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256 unavailable", impossible);
        }
    }

    private EvidenceAdmissionAuthority invalid(String blocker) {
        return new EvidenceAdmissionAuthority(
                false, 0, 0, 0, false, false, BigDecimal.ZERO, List.of(blocker));
    }
}
