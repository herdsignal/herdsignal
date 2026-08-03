package com.herdsignal.service.decision;

import java.time.LocalDate;
import java.util.Optional;

/** 관찰일 이후 자료를 사용하지 않는 시장·섹터 가격 맥락 공급자. */
@FunctionalInterface
public interface MarketSectorEvidenceProvider {
    Optional<MarketSectorEvidenceSnapshot> contextAsOf(
            String ticker,
            String sectorEtf,
            LocalDate asOfDate
    );
}
