package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.util.List;

/**
 * HERD Action Layer 응답 DTO.
 * HERD 점수와 지표 품질을 바탕으로 장기투자자가 참고할 행동 강도를 계산한다.
 */
@Getter
@Builder
public class ActionDecision {

    /** 행동 점수 (0~100) */
    private Integer actionScore;

    /** 행동 등급 (STRONG_ACTION / ACTION / WATCH / NO_ACTION) */
    private String actionGrade;

    /** 화면 표시용 행동 문구 */
    private String actionLabel;

    /** 권장 행동 비율 (0.00~0.30) */
    private BigDecimal actionRatio;

    /** 세부 국면 코드 */
    private String actionRegime;

    /** 세부 국면 표시 문구 */
    private String actionRegimeLabel;

    /** 행동 판단 근거 */
    private List<String> actionReasons;

    /** 보수적으로 봐야 하는 이유 */
    private List<String> actionWarnings;
}
