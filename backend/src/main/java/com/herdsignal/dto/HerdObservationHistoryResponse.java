package com.herdsignal.dto;

import java.util.List;

/** 최신순으로 제한된 S1 관찰 이력 응답. */
public record HerdObservationHistoryResponse(
        String availabilityStatus,
        String ticker,
        String stateModelVersion,
        List<HerdObservationHistoryPoint> points
) {}
