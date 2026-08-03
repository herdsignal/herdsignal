package com.herdsignal.dto;

import java.math.BigDecimal;
import java.util.List;

public record BusinessVetoProspectiveStatusResponse(
        String status,
        boolean registryValid,
        int addDirectionEvidenceAdmitted,
        int businessVetoEvidenceAdmitted,
        boolean collectionAllowed,
        String operationalAction,
        BigDecimal operationalActionRatio,
        List<String> blockers
) {
    public BusinessVetoProspectiveStatusResponse {
        blockers = blockers == null ? List.of() : List.copyOf(blockers);
    }
}
