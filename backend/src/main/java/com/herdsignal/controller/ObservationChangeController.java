package com.herdsignal.controller;

import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.ObservationChangesResponse;
import com.herdsignal.dto.ObservationSeenRequest;
import com.herdsignal.service.CurrentUserService;
import com.herdsignal.service.ObservationChangeService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/observation-changes")
@RequiredArgsConstructor
public class ObservationChangeController {
    private final ObservationChangeService service;
    private final CurrentUserService currentUserService;

    @GetMapping
    public ResponseEntity<ApiResponse<ObservationChangesResponse>> getChanges(
            @RequestParam(required = false) Integer limit
    ) {
        return ResponseEntity.ok(ApiResponse.success(
                service.getChanges(currentUserService.requireUserId(), limit)
        ));
    }

    @PostMapping("/{ticker}/seen")
    public ResponseEntity<ApiResponse<Void>> markTickerSeen(
            @PathVariable String ticker,
            @Valid @RequestBody ObservationSeenRequest request
    ) {
        service.markTickerSeen(
                currentUserService.requireUserId(),
                ticker,
                request.seenThroughDate()
        );
        return ResponseEntity.ok(ApiResponse.success(null));
    }

    @PostMapping("/seen-all")
    public ResponseEntity<ApiResponse<Void>> markAllSeen() {
        service.markAllSeen(currentUserService.requireUserId());
        return ResponseEntity.ok(ApiResponse.success(null));
    }
}
