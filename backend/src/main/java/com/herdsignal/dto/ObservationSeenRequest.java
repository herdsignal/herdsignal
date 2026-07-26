package com.herdsignal.dto;

import jakarta.validation.constraints.NotNull;

import java.time.LocalDate;

public record ObservationSeenRequest(
        @NotNull(message = "확인한 관찰일이 필요합니다.")
        LocalDate seenThroughDate
) {}
