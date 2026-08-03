package com.herdsignal.service.decision;

import com.herdsignal.service.EvidenceAdmissionAuthority;
import com.herdsignal.service.EvidenceAdmissionAuthorityService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

/** 판단 생성과 별개로 해시 검증된 채택 권한이 없는 행동을 최종 차단한다. */
@Component
public class OperatingActionAuthorizationGate {
    private final EvidenceAdmissionAuthorityService authorityService;
    private final EvidenceAdmissionAuthority fixedAuthority;

    @Autowired
    public OperatingActionAuthorizationGate(EvidenceAdmissionAuthorityService authorityService) {
        this.authorityService = authorityService;
        this.fixedAuthority = null;
    }

    OperatingActionAuthorizationGate(EvidenceAdmissionAuthority fixedAuthority) {
        this.authorityService = null;
        this.fixedAuthority = fixedAuthority;
    }

    static OperatingActionAuthorizationGate failClosed() {
        return new OperatingActionAuthorizationGate(new EvidenceAdmissionAuthority(
                false, 0, 0, 0, false, false, BigDecimal.ZERO,
                List.of("ACTION_AUTHORITY_NOT_CONNECTED")));
    }

    public DecisionSynthesis enforce(DecisionSynthesis requested) {
        if (requested == null) return denied(null, List.of("SYNTHESIS_MISSING"));
        boolean actionCode = requested.decision() == OperatingDecisionCode.REVIEW_ADD
                || requested.decision() == OperatingDecisionCode.REVIEW_TRIM;
        if (!actionCode && !requested.actionAuthorized()) return requested;
        EvidenceAdmissionAuthority authority = authority();
        List<String> blockers = new ArrayList<>(authority.blockers().stream()
                .filter(item -> !item.endsWith("_EVIDENCE_NOT_ADMITTED"))
                .filter(item -> !item.equals("BLIND_HOLDOUT_ALREADY_OPEN"))
                .toList());
        if (!requested.actionAuthorized()) blockers.add("REQUEST_NOT_AUTHORIZED");
        if (!authority.registryValid()) blockers.add("ADMISSION_REGISTRY_INVALID");
        if (!authority.operationalActionEnabled()) blockers.add("OPERATIONAL_ACTION_NOT_PROMOTED");
        if (requested.operationalActionRatio() <= 0) blockers.add("ACTION_RATIO_NOT_POSITIVE");
        if (BigDecimal.valueOf(requested.operationalActionRatio())
                .compareTo(authority.operationalActionRatio()) > 0) {
            blockers.add("ACTION_RATIO_EXCEEDS_AUTHORITY");
        }
        switch (requested.decision()) {
            case REVIEW_ADD -> {
                if (authority.reentrySupportCount() == 0) {
                    blockers.add("ADD_DIRECTION_EVIDENCE_NOT_ADMITTED");
                }
                if (authority.businessVetoCount() == 0) {
                    blockers.add("BUSINESS_VETO_EVIDENCE_NOT_ADMITTED");
                }
            }
            case REVIEW_TRIM -> {
                if (authority.profitTakeDirectionCount() == 0) {
                    blockers.add("TRIM_DIRECTION_EVIDENCE_NOT_ADMITTED");
                }
            }
            default -> blockers.add("DECISION_NOT_ACTION_ELIGIBLE");
        }
        return blockers.isEmpty() ? requested : denied(requested, blockers);
    }

    private EvidenceAdmissionAuthority authority() {
        return fixedAuthority != null ? fixedAuthority : authorityService.authority();
    }

    private DecisionSynthesis denied(DecisionSynthesis requested, List<String> blockers) {
        List<String> limitations = new ArrayList<>();
        if (requested != null) limitations.addAll(requested.limitations());
        blockers.stream().distinct().forEach(limitations::add);
        return new DecisionSynthesis(
                OperatingDecisionCode.OBSERVE,
                "운영 행동 권한 미승격",
                requested == null ? List.of() : requested.evidenceRefs(),
                limitations,
                false,
                "OBSERVE",
                0.0);
    }
}
