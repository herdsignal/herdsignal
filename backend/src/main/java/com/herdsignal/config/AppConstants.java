package com.herdsignal.config;

/**
 * 전역 상수 관리 클래스.
 * MVP에서 userId는 "local" 고정. 추후 인증 추가 시 이 파일만 수정.
 */
public class AppConstants {

    private AppConstants() { /* 인스턴스화 방지 */ }

    /** 기본 사용자 ID — MVP 단계 로컬 단일 사용자 */
    public static final String DEFAULT_USER_ID = "local";

    /** S&P500 벤치마크 사용자 ID — SPY 전용 */
    public static final String SPY_BENCHMARK_USER_ID = "spy_benchmark";
}
