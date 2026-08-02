package com.herdsignal.controller;

import com.herdsignal.dto.ApiResponse;
import com.herdsignal.service.decision.ObjectiveEvidenceService;
import com.herdsignal.service.decision.ObjectiveReviewResponse;
import com.herdsignal.service.decision.LongTermOperatingReviewService;
import com.herdsignal.service.decision.PersonalOperatingReviewResponse;
import com.herdsignal.service.decision.OperatingReviewSnapshotResponse;
import com.herdsignal.service.decision.OperatingReviewSnapshotService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** 검증된 근거만 노출하는 장기 운용 판단 API. */
@RestController
@RequestMapping("/api/operating-reviews")
@RequiredArgsConstructor
public class OperatingReviewController {
    private final ObjectiveEvidenceService objectiveEvidenceService;
    private final LongTermOperatingReviewService operatingReviewService;
    private final OperatingReviewSnapshotService snapshotService;

    @GetMapping("/{ticker}/objective")
    public ResponseEntity<ApiResponse<ObjectiveReviewResponse>> objective(
            @PathVariable String ticker
    ) {
        return ResponseEntity.ok(ApiResponse.success(objectiveEvidenceService.review(ticker)));
    }

    @GetMapping("/{ticker}")
    public ResponseEntity<ApiResponse<PersonalOperatingReviewResponse>> personal(
            @PathVariable String ticker
    ) {
        return ResponseEntity.ok(ApiResponse.success(operatingReviewService.review(ticker)));
    }

    @PostMapping("/{ticker}/records")
    public ResponseEntity<ApiResponse<OperatingReviewSnapshotResponse>> record(
            @PathVariable String ticker
    ) {
        return ResponseEntity.ok(ApiResponse.success(snapshotService.record(ticker)));
    }

    @GetMapping("/{ticker}/records")
    public ResponseEntity<ApiResponse<List<OperatingReviewSnapshotResponse>>> history(
            @PathVariable String ticker
    ) {
        return ResponseEntity.ok(ApiResponse.success(snapshotService.history(ticker)));
    }
}
