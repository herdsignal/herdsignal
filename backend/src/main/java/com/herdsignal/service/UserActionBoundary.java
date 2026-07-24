package com.herdsignal.service;

import org.springframework.stereotype.Component;

import java.math.BigDecimal;

/**
 * 사용자에게 노출되는 모델 행동의 단일 fail-closed 경계.
 *
 * 현재 운영 모델은 상태 관찰만 승인되어 있으므로, 연구 모델·저장 데이터·
 * 클라이언트 입력의 내용과 무관하게 행동 권한을 HOLD 0%로 고정한다.
 * 향후 모델 승격은 이 클래스를 우회하지 않고 별도 승격 포트가 발급한
 * 승인 결과를 이 경계에 연결해야 한다.
 */
@Component
public class UserActionBoundary {

    private static final BigDecimal ZERO_RATIO = new BigDecimal("0.0000");

    public Output locked() {
        return new Output("HOLD", ZERO_RATIO, false, false);
    }

    public Output fromApproved(GrantedOperationalAction grant) {
        if (grant == null) {
            return locked();
        }
        return new Output(grant.action(), grant.ratio(), true, true);
    }

    public record Output(
            String action,
            BigDecimal ratio,
            boolean authorized,
            boolean directionPrediction
    ) {
    }
}
