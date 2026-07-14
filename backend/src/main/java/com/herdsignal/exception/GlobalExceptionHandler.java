package com.herdsignal.exception;

import com.herdsignal.dto.ApiResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 전역 예외 처리 핸들러.
 * Controller에서 발생하는 모든 예외를 ApiResponse 형태로 통일해 반환.
 */
@RestControllerAdvice
@Slf4j
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
     * 잘못된 요청 값 → HTTP 400.
     * 티커 형식 오류, HERD 미준비 종목 추가 시도 등을 클라이언트에 명확히 반환.
     */
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ApiResponse<Void>> handleIllegalArgument(IllegalArgumentException e) {
        return ResponseEntity
                .status(HttpStatus.BAD_REQUEST)
                .body(ApiResponse.fail(e.getMessage()));
    }

    /** 검증 리포트 미생성·손상 → HTTP 503. */
    @ExceptionHandler(ModelReportUnavailableException.class)
    public ResponseEntity<ApiResponse<Void>> handleModelReportUnavailable(
            ModelReportUnavailableException e) {
        return ResponseEntity
                .status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(ApiResponse.fail(e.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Void>> handleValidation(MethodArgumentNotValidException e) {
        String message = e.getBindingResult().getFieldErrors().stream()
                .findFirst()
                .map(error -> error.getField() + ": " + error.getDefaultMessage())
                .orElse("요청 값을 확인해 주세요.");
        return ResponseEntity.badRequest().body(ApiResponse.fail(message));
    }

    /**
     * 나머지 모든 예외 → HTTP 500.
     * 예상치 못한 서버 오류를 클라이언트에게 안전하게 반환.
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleException(Exception e) {
        String errorId = java.util.UUID.randomUUID().toString().substring(0, 8);
        log.error("예상하지 못한 서버 오류 [errorId={}]", errorId, e);
        return ResponseEntity
                .status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiResponse.fail("서버 내부 오류가 발생했습니다. 오류 ID: " + errorId));
    }
}
