package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

/**
 * 공통 API 응답 래퍼.
 * 모든 엔드포인트가 일관된 JSON 구조를 반환하도록 사용.
 *
 * 성공: { "success": true, "data": {...}, "message": null }
 * 실패: { "success": false, "data": null, "message": "오류 설명" }
 */
@Getter
@Builder
public class ApiResponse<T> {

    /** 요청 처리 성공 여부 */
    private final boolean success;

    /** 응답 데이터 (실패 시 null) */
    private final T data;

    /** 오류 메시지 (성공 시 null) */
    private final String message;

    /** 성공 응답 생성 */
    public static <T> ApiResponse<T> success(T data) {
        return ApiResponse.<T>builder()
                .success(true)
                .data(data)
                .build();
    }

    /** 실패 응답 생성 */
    public static <T> ApiResponse<T> fail(String message) {
        return ApiResponse.<T>builder()
                .success(false)
                .message(message)
                .build();
    }
}
