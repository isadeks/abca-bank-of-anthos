/*
 * Copyright 2026, Google LLC.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package anthos.samples.bankofanthos.transactionhistory;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;
import javax.sql.DataSource;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.data.jpa.repository.Query;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * Integration test proving the spending query reads the ledger through the
 * (FROM_ACCT, FROM_ROUTE, TIMESTAMP) index with a range on the timestamp,
 * so its cost depends on the months scanned and not on the whole history,
 * against the real ledger database (Postgres with the Bank of Anthos schema
 * and its indexes).
 *
 * An account with a long history (most of it older than the two months) is
 * stored next to many other accounts. The test checks the totals, and that
 * the plan Postgres picks for the query uses the sender index with the
 * timestamp in its index condition, never a sequential scan.
 *
 * Runs only when SPRING_DATASOURCE_URL, SPRING_DATASOURCE_USERNAME and
 * SPRING_DATASOURCE_PASSWORD are set. The ledger is append-only, so the test
 * uses freshly generated account numbers instead of cleaning up.
 */
class TransactionHistorySpendingQueryPlanIT {

    private static final String LOCAL_ROUTING_NUM = "883745000";
    private static final LocalDateTime FROM =
        LocalDateTime.of(2026, 2, 1, 0, 0);
    /** Rows of the account before the two months. */
    private static final int OLD_ROWS = 30_000;
    /** Rows of the account in the two months. */
    private static final int RECENT_ROWS = 2_000;
    /** Transactions of other accounts, so that the account is selective. */
    private static final int NOISE_ROWS = 100_000;

    private static AnnotationConfigApplicationContext context;
    private static JdbcTemplate jdbc;
    private static TransactionRepository repository;
    private static String account;

    @BeforeAll
    static void setUp() {
        context = new AnnotationConfigApplicationContext();
        context.register(LedgerDbTestConfig.class);
        context.refresh();
        jdbc = new JdbcTemplate(context.getBean(DataSource.class));
        repository = context.getBean(TransactionRepository.class);

        account = String.valueOf(
            ThreadLocalRandom.current().nextLong(1_000_000_000L,
                1_900_000_000L));
        // Other accounts: 2_000_000_000 and up, never the account.
        long noiseBase = ThreadLocalRandom.current().nextLong(
            2_000_000_000L, 8_000_000_000L);
        jdbc.update("INSERT INTO TRANSACTIONS (FROM_ACCT, TO_ACCT, "
            + "FROM_ROUTE, TO_ROUTE, AMOUNT, TIMESTAMP) "
            + "SELECT CAST(? + g AS TEXT), CAST(? + g + 1 AS TEXT), ?, ?, "
            + "1, TIMESTAMP '2026-03-01 00:00:00' - (g || ' seconds')::interval "
            + "FROM generate_series(1, ?) g",
            noiseBase, noiseBase, LOCAL_ROUTING_NUM, LOCAL_ROUTING_NUM,
            NOISE_ROWS);
        // Old rows: 1 cent each, one day or more before the two months.
        jdbc.update("INSERT INTO TRANSACTIONS (FROM_ACCT, TO_ACCT, "
            + "FROM_ROUTE, TO_ROUTE, AMOUNT, TIMESTAMP) "
            + "SELECT ?, CAST(? + (g % 5) AS TEXT), ?, ?, "
            + "1, TIMESTAMP '2026-01-30 00:00:00' - (g || ' seconds')::interval "
            + "FROM generate_series(1, ?) g",
            account, noiseBase, LOCAL_ROUTING_NUM, LOCAL_ROUTING_NUM,
            OLD_ROWS);
        // Recent rows: 3 cents each, within the two months.
        jdbc.update("INSERT INTO TRANSACTIONS (FROM_ACCT, TO_ACCT, "
            + "FROM_ROUTE, TO_ROUTE, AMOUNT, TIMESTAMP) "
            + "SELECT ?, CAST(? + (g % 5) AS TEXT), ?, ?, "
            + "3, TIMESTAMP '2026-02-01 00:00:00' + (g || ' seconds')::interval "
            + "FROM generate_series(1, ?) g",
            account, noiseBase, LOCAL_ROUTING_NUM, LOCAL_ROUTING_NUM,
            RECENT_ROWS);
        // Give the planner the statistics it has in a real ledger.
        jdbc.execute("ANALYZE TRANSACTIONS");
    }

    @AfterAll
    static void tearDown() {
        if (context != null) {
            context.close();
        }
    }

    @Test
    @DisplayName("Only the rows from the given time onward are totalled, "
        + "however long the history of the account")
    void totalsCoverOnlyTheRequestedMonths() {
        List<Object[]> rows = repository.spendingByCounterparty(
            account, LOCAL_ROUTING_NUM, FROM);

        long total = rows.stream()
            .mapToLong(row -> ((Number) row[3]).longValue()).sum();
        assertEquals(3L * RECENT_ROWS, total);
        // Five counterparties in one month.
        assertEquals(5, rows.size());
    }

    @Test
    @DisplayName("The plan of the spending query uses the sender index with "
        + "a range on the timestamp and does not scan the whole ledger")
    void spendingQueryPlanUsesTheSenderIndex() {
        String plan = String.join("\n", jdbc.queryForList(
            "EXPLAIN " + spendingSql(account, LOCAL_ROUTING_NUM, FROM),
            String.class));

        assertTrue(plan.contains("Index"), plan);
        assertTrue(plan.contains("from_acct_from_route_timestamp_idx"), plan);
        assertTrue(plan.toLowerCase().contains("timestamp"), plan);
        assertFalse(plan.contains("Seq Scan"), plan);
    }

    /**
     * The repository's own query text with the parameters filled in, so the
     * plan checked is the plan of the query the service really runs.
     */
    private static String spendingSql(String acct, String route,
                                      LocalDateTime from) {
        try {
            String sql = TransactionRepository.class
                .getMethod("spendingByCounterparty", String.class,
                    String.class, LocalDateTime.class)
                .getAnnotation(Query.class)
                .value();
            sql = sql.replace("?1", "'" + acct.replace("'", "''") + "'");
            sql = sql.replace("?2", "'" + route.replace("'", "''") + "'");
            sql = sql.replace("?3", "'" + Timestamp.valueOf(from) + "'");
            return sql;
        } catch (NoSuchMethodException e) {
            throw new IllegalStateException(e);
        }
    }
}
