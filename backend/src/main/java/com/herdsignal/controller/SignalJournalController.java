package com.herdsignal.controller;

import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.SignalJournalRequest;
import com.herdsignal.dto.SignalJournalResponse;
import com.herdsignal.service.SignalJournalService;
import com.herdsignal.service.CurrentUserService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * HERD 판단 기록 API 컨트롤러.
 * 사용자 식별은 현재 로그인 세션에서 가져온다.
 */
@RestController
@RequestMapping("/api/journal")
@RequiredArgsConstructor
public class SignalJournalController {

    private final SignalJournalService signalJournalService;
    private final CurrentUserService currentUserService;

    @GetMapping
    public ResponseEntity<ApiResponse<List<SignalJournalResponse>>> getJournals(
            @RequestParam(required = false) String ticker) {
        List<SignalJournalResponse> response =
                signalJournalService.getJournals(currentUserService.requireUserId(), ticker);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    @PostMapping
    public ResponseEntity<ApiResponse<SignalJournalResponse>> createJournal(
            @RequestBody SignalJournalRequest request) {
        SignalJournalResponse response =
                signalJournalService.createJournal(currentUserService.requireUserId(), request);
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(response));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteJournal(@PathVariable Long id) {
        signalJournalService.deleteJournal(currentUserService.requireUserId(), id);
        return ResponseEntity.noContent().build();
    }
}
