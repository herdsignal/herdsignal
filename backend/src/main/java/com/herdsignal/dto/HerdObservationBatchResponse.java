package com.herdsignal.dto;

import java.util.List;

/** 요청 순서를 보존하는 HERD State S1 일괄 관찰 응답. */
public record HerdObservationBatchResponse(
        int requestedCount,
        int availableCount,
        List<HerdObservationResponse> observations
) {}
