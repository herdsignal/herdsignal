package com.herdsignal.service.decision;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;

/** 방향 예측 없이 시장·섹터·종목 고유 가격 경로를 분리한 시점 유효 관찰값. */
public record MarketSectorEvidenceSnapshot(
        String ticker,
        String sectorEtf,
        LocalDate asOfDate,
        OffsetDateTime observedAt,
        String sourceVersion,
        BigDecimal marketReturn63,
        BigDecimal marketDrawdown63,
        BigDecimal marketRealizedVolatility63,
        BigDecimal marketTrendVsSma200,
        BigDecimal sectorReturn63,
        BigDecimal sectorRelativeReturn63,
        BigDecimal sectorTrendVsSma200,
        BigDecimal stockReturn21,
        BigDecimal marketContribution21,
        BigDecimal sectorContribution21,
        BigDecimal stockSpecificContribution21,
        String downsideAttribution
) {
    public boolean hasMarketContext() {
        return marketReturn63 != null
                && marketDrawdown63 != null
                && marketRealizedVolatility63 != null
                && marketTrendVsSma200 != null;
    }

    public boolean hasSectorContext() {
        return sectorReturn63 != null
                && sectorRelativeReturn63 != null
                && sectorTrendVsSma200 != null;
    }

    public boolean hasStockAttribution() {
        return stockReturn21 != null
                && marketContribution21 != null
                && sectorContribution21 != null
                && stockSpecificContribution21 != null
                && downsideAttribution != null;
    }
}
