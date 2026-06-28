package com.herdsignal.exception;

import com.herdsignal.dto.ApiResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 전역 예외 처리 핸들러.
 * Controller에서 발생하는 모든 예외를 ApiResponse 형태로 통일해 반환.
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    /**
     * 리소스 미존재 예외 → HTTP 404.
     * HERD 데이터 없는 종목, 포트폴리오에 없는 종목 등.
     */
    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ApiResponse<Void>> handleResourceNotFound(ResourceNotFoundException e) {
        return ResponseEntity
                .status(HttpStatus.NOT_FOUND)
                .body(ApiResponse.fail(e.getMessage()));
    }

    /**
     * 중복 리소스 등록 예외 → HTTP 409.
     * 이미 포트폴리오에 있는 종목을 다시 추가하려 할 때.
     */
    @ExceptionHandler(DuplicateResourceException.class)
    public ResponseEntity<ApiResponse<Void>> handleDuplicate(DuplicateResourceException e) {
        return ResponseEntity
                .status(HttpStatus.CONFLICT)
                .body(ApiResponse.fail(e.getMessage()));
    }

    /**
     * 나머지 모든 예외 → HTTP 500.
     * 예상치 못한 서버 오류를 클라이언트에게 안전하게 반환.
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleException(Exception e) {
        return ResponseEntity
                .status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiResponse.fail("서버 내부 오류: " + e.getMessage()));
    }
}
