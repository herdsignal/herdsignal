package com.herdsignal.exception;

/**
 * 요청한 리소스가 DB에 존재하지 않을 때 발생.
 * GlobalExceptionHandler가 HTTP 404로 변환한다.
 */
public class ResourceNotFoundException extends RuntimeException {

    public ResourceNotFoundException(String message) {
        super(message);
    }
}
