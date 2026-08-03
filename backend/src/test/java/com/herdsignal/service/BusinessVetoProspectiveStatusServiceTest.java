package com.herdsignal.service;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class BusinessVetoProspectiveStatusServiceTest {

    @Test
    void blocksCollectionWhenEitherIndependentPrerequisiteIsMissing() {
        EvidenceAdmissionAuthorityService authorityService = mock(
                EvidenceAdmissionAuthorityService.class);
        when(authorityService.authority()).thenReturn(new EvidenceAdmissionAuthority(
                true, 0, 0, 0, false, false, BigDecimal.ZERO,
                List.of("ADD_DIRECTION_EVIDENCE_NOT_ADMITTED",
                        "BUSINESS_VETO_EVIDENCE_NOT_ADMITTED")));

        var response = new BusinessVetoProspectiveStatusService(authorityService).getStatus();

        assertThat(response.status()).isEqualTo("BLOCKED_PREREQUISITES");
        assertThat(response.collectionAllowed()).isFalse();
        assertThat(response.operationalAction()).isEqualTo("HOLD");
        assertThat(response.operationalActionRatio()).isZero();
    }
}
