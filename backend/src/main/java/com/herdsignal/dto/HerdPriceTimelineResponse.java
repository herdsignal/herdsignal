package com.herdsignal.dto;

import java.util.List;

/** 가격과 HERD를 동일 시간축으로 제공하는 읽기 전용 응답. */
public record HerdPriceTimelineResponse(
        String availabilityStatus,
        String ticker,
        String stateModelVersion,
        String priceField,
        int observationCount,
        int pricedObservationCount,
        List<HerdPriceTimelinePoint> points
) {}
