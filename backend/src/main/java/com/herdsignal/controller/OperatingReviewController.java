package com.herdsignal.controller;

import com.herdsignal.dto.ApiResponse;
import com.herdsignal.service.decision.ObjectiveEvidenceService;
import com.herdsignal.service.decision.ObjectiveReviewResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** 검증된 근거만 노출하는 장기 운용 판단 API. */
@RestController
@RequestMapping("/api/operating-reviews")
@RequiredArgsConstructor
public class OperatingReviewController {
    private final ObjectiveEvidenceService objectiveEvidenceService;

    @GetMapping("/{ticker}/objective")
    public ResponseEntity<ApiResponse<ObjectiveReviewResponse>> objective(
            @PathVariable String ticker
    ) {
        return ResponseEntity.ok(ApiResponse.success(objectiveEvidenceService.review(ticker)));
    }
}
