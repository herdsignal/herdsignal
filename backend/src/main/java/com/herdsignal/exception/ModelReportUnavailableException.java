package com.herdsignal.exception;

/** 검증 리포트 파일이 없거나 읽을 수 없을 때 발생한다. */
public class ModelReportUnavailableException extends RuntimeException {
    public ModelReportUnavailableException(String message) {
        super(message);
    }

    public ModelReportUnavailableException(String message, Throwable cause) {
        super(message, cause);
    }
}
