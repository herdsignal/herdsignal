package com.herdsignal.service.decision;

import java.time.LocalDate;
import java.util.Optional;

/** 가격 관찰일 이전에 공개된 가장 최근 기업 사실을 찾는다. */
public interface PitBusinessEvidenceProvider {
    Optional<BusinessEvidenceSnapshot> latestAsOf(String ticker, LocalDate observationDate);
}
