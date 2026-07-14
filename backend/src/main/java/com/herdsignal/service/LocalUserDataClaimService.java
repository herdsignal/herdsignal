package com.herdsignal.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/** 개인 프로젝트의 기존 local 데이터를 지정한 Google 계정에 한 번 연결한다. */
@Slf4j
@Service
@RequiredArgsConstructor
public class LocalUserDataClaimService {
    private static final List<String> USER_TABLES = List.of(
            "user_portfolio", "user_watchlist", "user_cash_balance", "user_cash_history",
            "portfolio_history", "signal_journal", "investor_profiles"
    );

    private final JdbcTemplate jdbcTemplate;

    @Value("${herdsignal.auth.owner-email:}")
    private String ownerEmail;

    @Transactional
    public void claimIfOwner(String email, String userId) {
        if (ownerEmail == null || ownerEmail.isBlank() || !ownerEmail.equalsIgnoreCase(email)) return;

        boolean targetAlreadyInitialized = USER_TABLES.stream().anyMatch(table ->
                count(table, userId) > 0);
        if (targetAlreadyInitialized) return;

        int moved = 0;
        for (String table : USER_TABLES) {
            moved += jdbcTemplate.update("UPDATE " + table + " SET user_id = ? WHERE user_id = 'local'", userId);
        }
        if (moved > 0) {
            log.info("기존 local 사용자 데이터 {}건을 로그인 사용자에게 연결했습니다.", moved);
        }
    }

    private int count(String table, String userId) {
        Integer count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM " + table + " WHERE user_id = ?", Integer.class, userId);
        return count == null ? 0 : count;
    }
}
