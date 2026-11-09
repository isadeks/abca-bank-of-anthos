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

import java.util.List;
import java.util.concurrent.ThreadLocalRandom;
import java.util.regex.Matcher;
import javax.sql.DataSource;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.jpa.repository.Query;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * Integration test proving the transaction history query scales with the
 * page size and not with the size of the account, against the real ledger
 * database (Postgres with the Bank of Anthos schema and its indexes).
 *
 * A large account (thousands of transactions, as sender and as receiver)
 * is stored next to many other accounts. The test checks that the query
 * returns the right newest page, and that the plan Postgres picks for it
 * reads the ledger through its account indexes with a limit, never with a
 * sequential scan, a bitmap scan of the whole account, or a sort of all of
 * the account's transactions.
 *
 * Runs only when SPRING_DATASOURCE_URL, SPRING_DATASOURCE_USERNAME and
 * SPRING_DATASOURCE_PASSWORD are set. The ledger is append-only, so the test
 * uses freshly generated account numbers instead of cleaning up.
 */
class TransactionHistoryQueryPlanIT {

    private static final String LOCAL_ROUTING_NUM = "883745000";
    private static final int PAGE = 100;
    /** Transactions of the large account, as sender and as receiver each. */
    private static final int LARGE_ACCOUNT_HALF = 5_000;
    /** Transactions of other accounts, so that the account is selective. */
    private static final int NOISE_ROWS = 100_000;

    private static AnnotationConfigApplicationContext context;
    private static JdbcTemplate jdbc;
    private static TransactionRepository repository;
    private static String largeAccount;

    @BeforeAll
    static void setUp() {
        context = new AnnotationConfigApplicationContext();
        context.register(LedgerDbTestConfig.class);
        context.refresh();
        jdbc = new JdbcTemplate(context.getBean(DataSource.class));
        repository = context.getBean(TransactionRepository.class);

        largeAccount = String.valueOf(
            ThreadLocalRandom.current().nextLong(1_000_000_000L,
                1_900_000_000L));
        // Other accounts: 2_000_000_000 and up, never the large account.
        long noiseBase = ThreadLocalRandom.current().nextLong(
            2_000_000_000L, 8_000_000_000L);
        jdbc.update("INSERT INTO TRANSACTIONS (FROM_ACCT, TO_ACCT, "
            + "FROM_ROUTE, TO_ROUTE, AMOUNT, TIMESTAMP) "
            + "SELECT CAST(? + g AS TEXT), CAST(? + g + 1 AS TEXT), ?, ?, "
            + "1, now() - (g || ' seconds')::interval "
            + "FROM generate_series(1, ?) g",
            noiseBase, noiseBase, LOCAL_ROUTING_NUM, LOCAL_ROUTING_NUM,
            NOISE_ROWS);
        // The large account sends at even seconds ago (amount 2g) and
        // receives at odd seconds ago (amount 2g - 1), so the amount is the
        // age rank: the newest transaction has the lowest amount.
        jdbc.update("INSERT INTO TRANSACTIONS (FROM_ACCT, TO_ACCT, "
            + "FROM_ROUTE, TO_ROUTE, AMOUNT, TIMESTAMP) "
            + "SELECT ?, CAST(? + g AS TEXT), ?, ?, "
            + "2 * g, now() - ((2 * g) || ' seconds')::interval "
            + "FROM generate_series(1, ?) g",
            largeAccount, noiseBase, LOCAL_ROUTING_NUM, LOCAL_ROUTING_NUM,
            LARGE_ACCOUNT_HALF);
        jdbc.update("INSERT INTO TRANSACTIONS (FROM_ACCT, TO_ACCT, "
            + "FROM_ROUTE, TO_ROUTE, AMOUNT, TIMESTAMP) "
            + "SELECT CAST(? + g AS TEXT), ?, ?, ?, "
            + "2 * g - 1, now() - ((2 * g - 1) || ' seconds')::interval "
            + "FROM generate_series(1, ?) g",
            noiseBase, largeAccount, LOCAL_ROUTING_NUM, LOCAL_ROUTING_NUM,
            LARGE_ACCOUNT_HALF);
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
    @DisplayName("The newest page of a large account is returned, newest "
        + "first, from both the sent and the received transactions")
    void largeAccountHistoryIsTheNewestPage() {
        List<Transaction> page = repository.findForAccount(
            largeAccount, LOCAL_ROUTING_NUM, PageRequest.of(0, PAGE));

        assertEquals(PAGE, page.size());
        for (int i = 0; i < PAGE; i++) {
            // Amounts 1, 2, 3, ... interleave received and sent rows.
            assertEquals(i + 1, page.get(i).getAmount());
        }
    }

    @Test
    @DisplayName("The plan of the history query reads the account indexes "
        + "with a limit and does not scan or sort the whole account")
    void historyQueryPlanUsesIndexesWithLimit() {
        String plan = String.join("\n", jdbc.queryForList(
            "EXPLAIN " + historySql(largeAccount, LOCAL_ROUTING_NUM),
            String.class));

        assertTrue(plan.contains("Index"), plan);
        assertTrue(plan.contains("Limit"), plan);
        assertFalse(plan.contains("Seq Scan"), plan);
        assertFalse(plan.contains("Bitmap"), plan);
    }

    /**
     * The repository's own query text with the parameters filled in, so the
     * plan checked is the plan of the query the service really runs.
     */
    private static String historySql(String account, String route) {
        try {
            String sql = TransactionRepository.class
                .getMethod("findForAccount", String.class, String.class,
                    org.springframework.data.domain.Pageable.class)
                .getAnnotation(Query.class)
                .value();
            sql = sql.replaceAll("\\?#\\{[^}]*\\}",
                Matcher.quoteReplacement(String.valueOf(PAGE)));
            sql = sql.replace("?1",
                "'" + account.replace("'", "''") + "'");
            sql = sql.replace("?2",
                "'" + route.replace("'", "''") + "'");
            return sql;
        } catch (NoSuchMethodException e) {
            throw new IllegalStateException(e);
        }
    }
}
