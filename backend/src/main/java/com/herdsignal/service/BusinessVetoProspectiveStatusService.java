package com.herdsignal.service;

import com.herdsignal.dto.BusinessVetoProspectiveStatusResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;

/** 추가매수 후보와 기업 veto가 모두 채택되기 전에는 전향 시험도 시작하지 않는다. */
@Service
@RequiredArgsConstructor
public class BusinessVetoProspectiveStatusService {
    private final EvidenceAdmissionAuthorityService authorityService;

    public BusinessVetoProspectiveStatusResponse getStatus() {
        EvidenceAdmissionAuthority authority = authorityService.authority();
        boolean allowed = authority.addVetoProspectiveCollectionAllowed();
        return new BusinessVetoProspectiveStatusResponse(
                allowed ? "READY_TO_COLLECT" : "BLOCKED_PREREQUISITES",
                authority.registryValid(),
                authority.reentrySupportCount(),
                authority.businessVetoCount(),
                allowed,
                "HOLD",
                BigDecimal.ZERO,
                authority.blockers());
    }
}
