package com.herdsignal.dto;

import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

@Getter
@Builder
public class PortfolioPerformanceResponse {

    private String status;
    private String method;
    private String benchmark;
    private LocalDate startDate;
    private LocalDate endDate;
    private BigDecimal portfolioReturnPct;
    private BigDecimal benchmarkReturnPct;
    private BigDecimal excessReturnPct;
    private List<PortfolioPerformancePointResponse> points;
    private List<String> warnings;
    private List<String> errors;
}
