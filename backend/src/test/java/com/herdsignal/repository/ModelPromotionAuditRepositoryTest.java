package com.herdsignal.repository;

import com.herdsignal.domain.ModelPromotionAudit;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;

import java.math.BigDecimal;
import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
class ModelPromotionAuditRepositoryTest {

    @Autowired
    private ModelPromotionAuditRepository repository;

    @Test
    void preservesPromotionDecisionHistoryNewestFirst() {
        repository.save(audit("REJECTED", LocalDateTime.of(2026, 7, 24, 1, 0)));
        repository.save(audit("GRANTED", LocalDateTime.of(2026, 7, 25, 1, 0)));

        assertThat(repository.findByCandidateIdOrderByRequestedAtDesc("CANDIDATE_S2"))
                .extracting(ModelPromotionAudit::getDecision)
                .containsExactly("GRANTED", "REJECTED");
    }

    private ModelPromotionAudit audit(String decision, LocalDateTime requestedAt) {
        return ModelPromotionAudit.builder()
                .candidateId("CANDIDATE_S2")
                .modelVersion("HERD_ACTION_S2")
                .artifactSha256("a".repeat(64))
                .ticker("NVDA")
                .requestedAction("REDUCE")
                .requestedRatio(new BigDecimal("0.0500"))
                .decision(decision)
                .reasonCode("TEST")
                .requestedAt(requestedAt)
                .build();
    }
}
