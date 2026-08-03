package com.herdsignal.service;

import java.math.BigDecimal;
import java.util.List;

/** 해시 검증된 연구 채택 원장이 부여하는 런타임 권한. */
public record EvidenceAdmissionAuthority(
        boolean registryValid,
        int profitTakeDirectionCount,
        int reentrySupportCount,
        int businessVetoCount,
        boolean blindHoldoutOpen,
        boolean operationalActionEnabled,
        BigDecimal operationalActionRatio,
        List<String> blockers
) {
    public EvidenceAdmissionAuthority {
        blockers = blockers == null ? List.of() : List.copyOf(blockers);
    }

    public boolean addVetoProspectiveCollectionAllowed() {
        return registryValid && reentrySupportCount > 0 && businessVetoCount > 0;
    }
}
