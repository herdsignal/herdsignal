package com.herdsignal.repository;

import com.herdsignal.domain.ModelPromotionAudit;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ModelPromotionAuditRepository
        extends JpaRepository<ModelPromotionAudit, Long> {

    List<ModelPromotionAudit> findByCandidateIdOrderByRequestedAtDesc(
            String candidateId
    );
}
