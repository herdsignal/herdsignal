package com.herdsignal.controller;

import com.herdsignal.config.AppConstants;
import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.InvestorProfileRequest;
import com.herdsignal.dto.InvestorProfileResponse;
import com.herdsignal.service.InvestorProfileService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/investor-profile")
@RequiredArgsConstructor
public class InvestorProfileController {
    private final InvestorProfileService service;

    @GetMapping
    public ResponseEntity<ApiResponse<InvestorProfileResponse>> getProfile() {
        return ResponseEntity.ok(ApiResponse.success(service.get(AppConstants.DEFAULT_USER_ID)));
    }

    @PutMapping
    public ResponseEntity<ApiResponse<InvestorProfileResponse>> updateProfile(
            @RequestBody InvestorProfileRequest request) {
        return ResponseEntity.ok(ApiResponse.success(service.update(AppConstants.DEFAULT_USER_ID, request)));
    }
}
