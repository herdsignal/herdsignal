package com.herdsignal.config;

import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;

import java.sql.DriverManager;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class FlywayMigrationTest {

    @Test
    void initialMigrationCreatesEveryApplicationTable() throws Exception {
        String url = "jdbc:h2:mem:flyway;MODE=MariaDB;DB_CLOSE_DELAY=-1";
        Flyway flyway = Flyway.configure()
                .dataSource(url, "sa", "")
                .locations("classpath:db/migration")
                .load();

        assertThat(flyway.migrate().migrationsExecuted).isEqualTo(16);

        try (var connection = DriverManager.getConnection(url, "sa", "");
             var tables = connection.getMetaData().getTables(null, "PUBLIC", "%", new String[]{"TABLE"})) {
            Set<String> names = new java.util.HashSet<>();
            while (tables.next()) names.add(tables.getString("TABLE_NAME").toLowerCase());

            assertThat(names).contains(
                    "app_users", "stocks", "herd_scores", "herd_indicators", "daily_prices",
                    "user_portfolio", "investor_profiles", "user_watchlist", "user_cash_balance",
                    "user_cash_history", "portfolio_history", "signal_journal", "scheduler_runs",
                    "spring_session", "spring_session_attributes", "herd_observations",
                    "model_promotion_audits",
                    "user_observation_receipts",
                    "portfolio_ledger_entries",
                    "operating_review_snapshots",
                    "flyway_schema_history"
            );
        }

        try (var connection = DriverManager.getConnection(url, "sa", "");
             var columns = connection.getMetaData().getColumns(
                     null, "PUBLIC", "SCHEDULER_RUNS", "%")) {
            Set<String> names = new java.util.HashSet<>();
            while (columns.next()) names.add(columns.getString("COLUMN_NAME").toLowerCase());

            assertThat(names).contains("skipped_count", "skipped_tickers");
            assertThat(names).contains("universe_sha256", "publish_status");
            assertThat(names).contains("observation_count", "phase_results_json");
        }

        try (var connection = DriverManager.getConnection(url, "sa", "");
             var columns = connection.getMetaData().getColumns(
                     null, "PUBLIC", "MODEL_PROMOTION_AUDITS", "%")) {
            Map<String, String> types = new HashMap<>();
            while (columns.next()) {
                types.put(
                        columns.getString("COLUMN_NAME").toLowerCase(),
                        columns.getString("TYPE_NAME").toUpperCase()
                );
            }

            assertThat(types.get("artifact_sha256")).startsWith("CHAR");
            assertThat(types.get("approval_file_sha256")).startsWith("CHAR");
        }

        try (var connection = DriverManager.getConnection(url, "sa", "");
             var columns = connection.getMetaData().getColumns(
                     null, "PUBLIC", "USER_PORTFOLIO", "%")) {
            Map<String, Integer> scales = new HashMap<>();
            while (columns.next()) {
                scales.put(
                        columns.getString("COLUMN_NAME").toLowerCase(),
                        columns.getInt("DECIMAL_DIGITS")
                );
            }

            assertThat(scales.get("avg_price")).isEqualTo(6);
            assertThat(scales.get("quantity")).isEqualTo(6);
        }

        try (var connection = DriverManager.getConnection(url, "sa", "");
             var columns = connection.getMetaData().getColumns(
                     null, "PUBLIC", "OPERATING_REVIEW_SNAPSHOTS", "%")) {
            Set<String> names = new java.util.HashSet<>();
            while (columns.next()) names.add(columns.getString("COLUMN_NAME").toLowerCase());

            assertThat(names).contains("payload_sha256", "record_sha256");
        }
    }
}
