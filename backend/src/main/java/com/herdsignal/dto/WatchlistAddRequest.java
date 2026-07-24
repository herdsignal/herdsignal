package com.herdsignal.dto;

import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * 관심 종목 추가 요청 DTO.
 * ticker는 필수, memo는 선택.
 */
@Getter
@NoArgsConstructor
public class WatchlistAddRequest {

    /** 티커 심볼 (필수) — Service에서 대문자로 정규화 */
    @NotBlank(message = "티커는 필수입니다")
    @Pattern(regexp = "(?i)^[A-Z0-9.-]{1,10}$", message = "티커 형식이 올바르지 않습니다")
    private String ticker;

    /** 메모 (선택) */
    @Size(max = 200, message = "메모는 200자 이하여야 합니다")
    private String memo;
}
