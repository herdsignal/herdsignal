package com.herdsignal.controller;

import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.ModelValidationReportResponse;
import com.herdsignal.dto.ProspectiveEvidenceStatusResponse;
import com.herdsignal.dto.ShadowModelStatusResponse;
import com.herdsignal.dto.VNextModelStatusResponse;
import com.herdsignal.dto.BusinessVetoProspectiveStatusResponse;
import com.herdsignal.service.ModelValidationReportService;
import com.herdsignal.service.ProspectiveEvidenceStatusService;
import com.herdsignal.service.ShadowModelStatusService;
import com.herdsignal.service.VNextModelStatusService;
import com.herdsignal.service.BusinessVetoProspectiveStatusService;
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
    private final VNextModelStatusService vNextModelStatusService;
    private final ProspectiveEvidenceStatusService prospectiveEvidenceStatusService;
    private final BusinessVetoProspectiveStatusService businessVetoProspectiveStatusService;

    @GetMapping("/validation")
    public ResponseEntity<ApiResponse<ModelValidationReportResponse>> getValidationReport() {
        return ResponseEntity.ok(ApiResponse.success(reportService.getReport()));
    }

    @GetMapping("/shadow-status")
    public ResponseEntity<ApiResponse<ShadowModelStatusResponse>> getShadowStatus() {
        return ResponseEntity.ok(ApiResponse.success(shadowModelStatusService.getStatus()));
    }

    @GetMapping("/vnext-status")
    public ResponseEntity<ApiResponse<VNextModelStatusResponse>> getVNextStatus() {
        return ResponseEntity.ok(ApiResponse.success(vNextModelStatusService.getStatus()));
    }

    @GetMapping("/prospective-status")
    public ResponseEntity<ApiResponse<ProspectiveEvidenceStatusResponse>> getProspectiveStatus() {
        return ResponseEntity.ok(ApiResponse.success(prospectiveEvidenceStatusService.getStatus()));
    }

    @GetMapping("/business-veto-prospective-status")
    public ResponseEntity<ApiResponse<BusinessVetoProspectiveStatusResponse>>
    getBusinessVetoProspectiveStatus() {
        return ResponseEntity.ok(ApiResponse.success(businessVetoProspectiveStatusService.getStatus()));
    }
}
