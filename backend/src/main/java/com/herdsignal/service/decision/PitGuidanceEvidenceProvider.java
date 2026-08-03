package com.herdsignal.service.decision;

import java.time.LocalDate;
import java.util.List;

public interface PitGuidanceEvidenceProvider {
    List<GuidanceEvidenceFactSnapshot> latestAccessionAsOf(String ticker, LocalDate observationDate);
}
