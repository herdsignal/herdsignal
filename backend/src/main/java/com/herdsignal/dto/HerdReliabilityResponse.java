package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

/**
 * HERD 신호 신뢰도 응답 DTO.
 * 저장된 HERD 히스토리와 가격 데이터를 기반으로 on-demand 계산한다.
 */
@Getter
@Builder
public class HerdReliabilityResponse {

    private String ticker;
    private String modelVersion;
    private Integer periodYears;
    private Integer historyCount;

    private Integer fleeSampleSize;
    private Double fleeHitRate;
    private Integer rushSampleSize;
    private Double rushHitRate;

    private Double mddImprovement;
    private Double returnPreservation;
    private Double annualActions;
    private Double strategyReturn;
    private Double buyHoldReturn;
    private Double strategyMdd;
    private Double buyHoldMdd;

    private String reliabilityGrade;
    private String reliabilityLabel;
    private String summary;
    private String lastUpdated;
}
