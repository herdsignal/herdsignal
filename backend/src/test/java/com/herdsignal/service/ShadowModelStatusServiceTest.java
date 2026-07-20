package com.herdsignal.service;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ShadowModelStatusServiceTest {

    @Test
    void failedResearchGateKeepsShadowDisabled() {
        ShadowModelStatusService service = new ShadowModelStatusService(false, "", false);

        var result = service.getStatus();

        assertThat(result.shadowStatus()).isEqualTo("DISABLED_RESEARCH_GATE_FAILED");
        assertThat(result.productionOutputUnaffected()).isTrue();
        assertThat(result.userActionSuppressed()).isTrue();
    }

    @Test
    void enabledFlagCannotBypassHoldoutGate() {
        ShadowModelStatusService service = new ShadowModelStatusService(true, "B3", false);

        assertThat(service.getStatus().shadowStatus()).isEqualTo("BLOCKED_INVALID_CONFIGURATION");
    }

    @Test
    void flagsCannotBypassMissingPromotionApproval() {
        ShadowModelStatusService service = new ShadowModelStatusService(
                true, "B3", true, ignored -> false
        );

        assertThat(service.getStatus().shadowStatus())
                .isEqualTo("BLOCKED_INVALID_CONFIGURATION");
    }

    @Test
    void qualifiedCandidateCanOnlyEnterShadowMode() {
        ShadowModelStatusService service = new ShadowModelStatusService(true, "B5", true);

        var result = service.getStatus();

        assertThat(result.shadowStatus()).isEqualTo("SHADOW_ACTIVE");
        assertThat(result.productionOutputUnaffected()).isTrue();
        assertThat(result.userActionSuppressed()).isTrue();
    }
}
