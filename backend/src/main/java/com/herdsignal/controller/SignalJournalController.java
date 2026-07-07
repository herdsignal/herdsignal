package com.herdsignal.controller;

import com.herdsignal.config.AppConstants;
import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.SignalJournalRequest;
import com.herdsignal.dto.SignalJournalResponse;
import com.herdsignal.service.SignalJournalService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * HERD 판단 기록 API 컨트롤러.
 * MVP에서는 userId를 AppConstants.DEFAULT_USER_ID로 고정한다.
 */
@RestController
@RequestMapping("/api/journal")
@RequiredArgsConstructor
public class SignalJournalController {

    private final SignalJournalService signalJournalService;

    @GetMapping
    public ResponseEntity<ApiResponse<List<SignalJournalResponse>>> getJournals(
            @RequestParam(required = false) String ticker) {
        List<SignalJournalResponse> response =
                signalJournalService.getJournals(AppConstants.DEFAULT_USER_ID, ticker);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    @PostMapping
    public ResponseEntity<ApiResponse<SignalJournalResponse>> createJournal(
            @RequestBody SignalJournalRequest request) {
        SignalJournalResponse response =
                signalJournalService.createJournal(AppConstants.DEFAULT_USER_ID, request);
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(response));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteJournal(@PathVariable Long id) {
        signalJournalService.deleteJournal(AppConstants.DEFAULT_USER_ID, id);
        return ResponseEntity.noContent().build();
    }
}
