package com.herdsignal.exception;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class GlobalExceptionHandlerTest {

    @Test
    void unexpectedErrorDoesNotExposeInternalMessage() {
        var response = new GlobalExceptionHandler()
                .handleException(new RuntimeException("database-password-leak"));

        assertThat(response.getStatusCode().value()).isEqualTo(500);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().getMessage())
                .startsWith("서버 내부 오류가 발생했습니다. 오류 ID:")
                .doesNotContain("database-password-leak");
    }
}
