package com.herdsignal.controller;

import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.EvidenceReviewResponse;
import com.herdsignal.service.EvidenceReviewService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/research/evidence-reviews")
@RequiredArgsConstructor
public class EvidenceReviewController {
    private final EvidenceReviewService service;

    @PostMapping("/{ticker}")
    public ResponseEntity<ApiResponse<EvidenceReviewResponse>> review(
            @PathVariable String ticker
    ) {
        return ResponseEntity.ok(ApiResponse.success(service.review(ticker)));
    }
}
