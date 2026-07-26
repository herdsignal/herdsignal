package com.herdsignal.controller;

import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.DataFreshnessResponse;
import com.herdsignal.service.DataFreshnessService;
import com.herdsignal.service.SchedulerOperationsService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/system")
@RequiredArgsConstructor
public class SystemStatusController {
    private final DataFreshnessService dataFreshnessService;
    private final SchedulerOperationsService schedulerOperationsService;

    @GetMapping("/data-status")
    public ResponseEntity<ApiResponse<DataFreshnessResponse>> getDataStatus() {
        return ResponseEntity.ok(ApiResponse.success(dataFreshnessService.getStatus()));
    }

    @PostMapping("/scheduler/run")
    public ResponseEntity<ApiResponse<String>> requestSchedulerRun() {
        if (!schedulerOperationsService.requestManualRun()) {
            return ResponseEntity.status(HttpStatus.CONFLICT)
                    .body(ApiResponse.fail("이미 수동 갱신이 요청됐거나 실행 중입니다."));
        }
        return ResponseEntity.accepted()
                .body(ApiResponse.success("전체 데이터 갱신을 시작했습니다."));
    }
}
