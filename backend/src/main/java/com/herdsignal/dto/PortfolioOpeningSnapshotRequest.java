package com.herdsignal.dto;

import jakarta.validation.constraints.NotNull;

import java.time.LocalDate;

public record PortfolioOpeningSnapshotRequest(
        @NotNull LocalDate occurredOn
) {}
