package com.herdsignal.controller;

import com.herdsignal.dto.ApiResponse;
import com.herdsignal.dto.PortfolioLedgerEntryRequest;
import com.herdsignal.dto.PortfolioLedgerEntryResponse;
import com.herdsignal.service.CurrentUserService;
import com.herdsignal.service.PortfolioLedgerService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.PathVariable;

import java.util.List;

@RestController
@RequestMapping("/api/portfolio/ledger")
@RequiredArgsConstructor
public class PortfolioLedgerController {

    private final PortfolioLedgerService ledgerService;
    private final CurrentUserService currentUserService;

    @GetMapping
    public ResponseEntity<ApiResponse<List<PortfolioLedgerEntryResponse>>> getEntries(
            @RequestParam(required = false) String ticker
    ) {
        return ResponseEntity.ok(ApiResponse.success(
                ledgerService.getEntries(currentUserService.requireUserId(), ticker)
        ));
    }

    @PostMapping
    public ResponseEntity<ApiResponse<PortfolioLedgerEntryResponse>> create(
            @Valid @RequestBody PortfolioLedgerEntryRequest request
    ) {
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(
                ledgerService.create(currentUserService.requireUserId(), request)
        ));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        ledgerService.delete(currentUserService.requireUserId(), id);
        return ResponseEntity.noContent().build();
    }
}
