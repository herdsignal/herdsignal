package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDate;

@Getter
@Builder
public class PortfolioPerformancePointResponse {

    private LocalDate date;
    private BigDecimal portfolioIndex;
    private BigDecimal benchmarkIndex;
}
