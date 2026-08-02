package com.herdsignal.service;

import com.herdsignal.dto.EvidenceReviewResponse;

import java.util.List;

public interface EvidenceReviewGateway {
    boolean isEnabled();
    String model();
    Draft review(Packet packet, String safetyIdentifier);

    record Packet(
            String ticker,
            String scope,
            List<EvidenceReviewResponse.EvidenceFact> evidence
    ) {}

    record Draft(
            List<EvidenceReviewResponse.Lens> lenses,
            String summary,
            List<String> disagreements,
            List<String> factsToVerify,
            boolean directionPrediction,
            String operationalAction,
            double operationalActionRatio
    ) {}
}
