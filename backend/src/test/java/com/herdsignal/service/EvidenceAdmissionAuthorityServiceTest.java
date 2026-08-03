package com.herdsignal.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;

class EvidenceAdmissionAuthorityServiceTest {

    @TempDir
    Path tempDir;

    @Test
    void readsCurrentPinnedRegistryAndKeepsActionPrerequisitesBlocked() {
        EvidenceAdmissionAuthority authority = new EvidenceAdmissionAuthorityService(
                new ObjectMapper(), "../data/herd/model_evidence_admission_v1.json")
                .authority();

        assertThat(authority.registryValid()).isTrue();
        assertThat(authority.profitTakeDirectionCount()).isZero();
        assertThat(authority.reentrySupportCount()).isZero();
        assertThat(authority.businessVetoCount()).isZero();
        assertThat(authority.addVetoProspectiveCollectionAllowed()).isFalse();
        assertThat(authority.operationalActionRatio()).isZero();
        assertThat(authority.blockers()).contains(
                "ADD_DIRECTION_EVIDENCE_NOT_ADMITTED",
                "BUSINESS_VETO_EVIDENCE_NOT_ADMITTED");
    }

    @Test
    void failsClosedWhenReferencedResultHashDoesNotMatch() throws Exception {
        Path root = tempDir.resolve("project");
        Path registry = root.resolve("data/herd/registry.json");
        Path result = root.resolve("data/reports/result.json");
        Files.createDirectories(registry.getParent());
        Files.createDirectories(result.getParent());
        Files.writeString(result, "{}");
        Files.writeString(registry, """
                {
                  "registry_version":"HERD_MODEL_EVIDENCE_ADMISSION_V1",
                  "families":[{
                    "id":"TEST", "result_path":"data/reports/result.json",
                    "result_sha256":"wrong", "role":"REENTRY_SUPPORT",
                    "decision":"ADMITTED", "admitted":true
                  }],
                  "admission_summary":{
                    "direction_evidence_admitted":0,
                    "reentry_support_admitted":1,
                    "business_veto_admitted":0
                  },
                  "claim_boundary":{
                    "blind_holdout_access":false,
                    "next_stage_may_execute_trades":false,
                    "operational_action_ratio":0.0
                  }
                }
                """);

        EvidenceAdmissionAuthority authority = new EvidenceAdmissionAuthorityService(
                new ObjectMapper(), registry.toString()).authority();

        assertThat(authority.registryValid()).isFalse();
        assertThat(authority.addVetoProspectiveCollectionAllowed()).isFalse();
        assertThat(authority.blockers()).contains("SOURCE_HASH_INVALID:TEST");
    }
}
