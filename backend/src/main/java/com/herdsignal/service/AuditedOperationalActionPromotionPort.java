package com.herdsignal.service;

import com.herdsignal.domain.ModelPromotionAudit;
import com.herdsignal.repository.ModelPromotionAuditRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.Locale;
import java.util.Optional;

/**
 * 모델·산출물·holdout·사람 승인 근거를 대조하고 감사 행 저장에 성공한
 * 경우에만 최대 5%의 부분 행동 권한을 발급한다.
 */
@Service
public class AuditedOperationalActionPromotionPort
        implements OperationalActionPromotionPort {

    private static final BigDecimal MAX_RATIO = new BigDecimal("0.0500");
    private static final String SHA256_PATTERN = "(?i)^[0-9a-f]{64}$";
    private static final String TICKER_PATTERN = "^[A-Z][A-Z0-9.-]{0,9}$";

    private final OperationalPromotionGate promotionGate;
    private final ModelPromotionAuditRepository auditRepository;
    private final Clock clock;

    @Autowired
    public AuditedOperationalActionPromotionPort(
            OperationalPromotionGate promotionGate,
            ModelPromotionAuditRepository auditRepository
    ) {
        this(promotionGate, auditRepository, Clock.systemUTC());
    }

    AuditedOperationalActionPromotionPort(
            OperationalPromotionGate promotionGate,
            ModelPromotionAuditRepository auditRepository,
            Clock clock
    ) {
        this.promotionGate = promotionGate;
        this.auditRepository = auditRepository;
        this.clock = clock;
    }

    @Override
    @Transactional
    public Optional<GrantedOperationalAction> request(
            OperationalActionPromotionRequest request
    ) {
        Validation validation = validateRequest(request);
        PromotionEvidence evidence = request == null
                ? null
                : promotionGate.approvalEvidence(request.candidateId()).orElse(null);
        if (validation.valid() && evidence == null) {
            validation = Validation.reject("APPROVAL_EVIDENCE_MISSING");
        }
        if (validation.valid()
                && !evidence.modelVersion().equals(request.modelVersion())) {
            validation = Validation.reject("MODEL_VERSION_MISMATCH");
        }
        if (validation.valid()
                && !evidence.artifactSha256().equalsIgnoreCase(
                        request.artifactSha256()
                )) {
            validation = Validation.reject("ARTIFACT_HASH_MISMATCH");
        }

        boolean auditSaved = saveAudit(request, evidence, validation);
        if (!validation.valid() || !auditSaved) {
            return Optional.empty();
        }
        return Optional.of(new IssuedAction(request));
    }

    private Validation validateRequest(OperationalActionPromotionRequest request) {
        if (request == null) return Validation.reject("REQUEST_MISSING");
        if (!StringUtils.hasText(request.candidateId())) {
            return Validation.reject("CANDIDATE_ID_MISSING");
        }
        if (!StringUtils.hasText(request.modelVersion())) {
            return Validation.reject("MODEL_VERSION_MISSING");
        }
        if (request.artifactSha256() == null
                || !request.artifactSha256().matches(SHA256_PATTERN)) {
            return Validation.reject("ARTIFACT_HASH_INVALID");
        }
        if (request.ticker() == null
                || !request.ticker().matches(TICKER_PATTERN)) {
            return Validation.reject("TICKER_INVALID");
        }
        if (!"ADD".equals(request.action())
                && !"REDUCE".equals(request.action())) {
            return Validation.reject("PARTIAL_ACTION_ONLY");
        }
        if (request.ratio() == null
                || request.ratio().compareTo(BigDecimal.ZERO) <= 0
                || request.ratio().compareTo(MAX_RATIO) > 0) {
            return Validation.reject("RATIO_OUT_OF_RANGE");
        }
        LocalDate today = LocalDate.now(clock);
        if (request.asOfDate() == null || request.asOfDate().isAfter(today)) {
            return Validation.reject("AS_OF_DATE_INVALID");
        }
        return Validation.grant();
    }

    private boolean saveAudit(
            OperationalActionPromotionRequest request,
            PromotionEvidence evidence,
            Validation validation
    ) {
        try {
            auditRepository.saveAndFlush(ModelPromotionAudit.builder()
                    .candidateId(textOrUnknown(
                            request == null ? null : request.candidateId()
                    ))
                    .modelVersion(safeText(
                            request == null ? null : request.modelVersion(), 80
                    ))
                    .artifactSha256(safeHash(
                            request == null ? null : request.artifactSha256()
                    ))
                    .ticker(safeText(
                            request == null ? null : request.ticker(), 10
                    ))
                    .requestedAction(safeText(
                            request == null ? null : request.action(), 10
                    ))
                    .requestedRatio(safeRatio(
                            request == null ? null : request.ratio()
                    ))
                    .decision(validation.valid() ? "GRANTED" : "REJECTED")
                    .reasonCode(validation.reasonCode())
                    .policyVersion(evidence == null ? null : evidence.policyVersion())
                    .reviewer(evidence == null ? null : evidence.reviewer())
                    .approvalFileSha256(evidence == null
                            ? null
                            : evidence.approvalFileSha256())
                    .approvedAt(evidence == null
                            ? null
                            : LocalDateTime.ofInstant(
                                    evidence.approvedAt(),
                                    ZoneOffset.UTC
                            ))
                    .requestedAt(LocalDateTime.now(clock))
                    .build());
            return true;
        } catch (RuntimeException ignored) {
            return false;
        }
    }

    private String textOrUnknown(String value) {
        return StringUtils.hasText(value)
                ? safeText(value, 80)
                : "UNKNOWN";
    }

    private String safeHash(String value) {
        return value != null && value.matches(SHA256_PATTERN)
                ? value.toLowerCase(Locale.ROOT)
                : null;
    }

    private String safeText(String value, int maxLength) {
        if (value == null) return null;
        String trimmed = value.trim();
        return trimmed.length() <= maxLength
                ? trimmed
                : trimmed.substring(0, maxLength);
    }

    private BigDecimal safeRatio(BigDecimal ratio) {
        return ratio != null
                && ratio.compareTo(BigDecimal.ZERO) >= 0
                && ratio.compareTo(BigDecimal.ONE) <= 0
                ? ratio
                : null;
    }

    private record Validation(boolean valid, String reasonCode) {
        static Validation grant() {
            return new Validation(true, "ALL_GATES_PASSED");
        }

        static Validation reject(String reasonCode) {
            return new Validation(false, reasonCode);
        }
    }

    static final class IssuedAction implements GrantedOperationalAction {
        private final OperationalActionPromotionRequest request;

        private IssuedAction(OperationalActionPromotionRequest request) {
            this.request = request;
        }

        @Override
        public String candidateId() {
            return request.candidateId();
        }

        @Override
        public String modelVersion() {
            return request.modelVersion();
        }

        @Override
        public String ticker() {
            return request.ticker();
        }

        @Override
        public String action() {
            return request.action();
        }

        @Override
        public BigDecimal ratio() {
            return request.ratio();
        }

        @Override
        public LocalDate asOfDate() {
            return request.asOfDate();
        }
    }
}
