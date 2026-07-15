package com.herdsignal.config;

import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;

import java.sql.DriverManager;
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

        assertThat(flyway.migrate().migrationsExecuted).isEqualTo(2);

        try (var connection = DriverManager.getConnection(url, "sa", "");
             var tables = connection.getMetaData().getTables(null, "PUBLIC", "%", new String[]{"TABLE"})) {
            Set<String> names = new java.util.HashSet<>();
            while (tables.next()) names.add(tables.getString("TABLE_NAME").toLowerCase());

            assertThat(names).contains(
                    "app_users", "stocks", "herd_scores", "herd_indicators", "daily_prices",
                    "user_portfolio", "investor_profiles", "user_watchlist", "user_cash_balance",
                    "user_cash_history", "portfolio_history", "signal_journal", "scheduler_runs",
                    "flyway_schema_history"
            );
        }
    }
}
