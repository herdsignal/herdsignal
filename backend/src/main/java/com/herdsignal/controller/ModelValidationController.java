package com.herdsignal.controller;

import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.ModelValidationReportResponse;
import com.herdsignal.dto.ShadowModelStatusResponse;
import com.herdsignal.service.ModelValidationReportService;
import com.herdsignal.service.ShadowModelStatusService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** HERD 모델 검증 결과 조회 API. */
@RestController
@RequestMapping("/api/model")
@RequiredArgsConstructor
public class ModelValidationController {
    private final ModelValidationReportService reportService;
    private final ShadowModelStatusService shadowModelStatusService;

    @GetMapping("/validation")
    public ResponseEntity<ApiResponse<ModelValidationReportResponse>> getValidationReport() {
        return ResponseEntity.ok(ApiResponse.success(reportService.getReport()));
    }

    @GetMapping("/shadow-status")
    public ResponseEntity<ApiResponse<ShadowModelStatusResponse>> getShadowStatus() {
        return ResponseEntity.ok(ApiResponse.success(shadowModelStatusService.getStatus()));
    }
}
