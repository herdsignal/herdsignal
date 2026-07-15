package com.herdsignal.controller;

import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.DataFreshnessResponse;
import com.herdsignal.service.DataFreshnessService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/system")
@RequiredArgsConstructor
public class SystemStatusController {
    private final DataFreshnessService dataFreshnessService;

    @GetMapping("/data-status")
    public ResponseEntity<ApiResponse<DataFreshnessResponse>> getDataStatus() {
        return ResponseEntity.ok(ApiResponse.success(dataFreshnessService.getStatus()));
    }
}
