package com.herdsignal.exception;

/**
 * 이미 존재하는 리소스를 중복 등록하려 할 때 발생.
 * GlobalExceptionHandler가 HTTP 409로 변환한다.
 */
public class DuplicateResourceException extends RuntimeException {

    public DuplicateResourceException(String message) {
        super(message);
    }
}
