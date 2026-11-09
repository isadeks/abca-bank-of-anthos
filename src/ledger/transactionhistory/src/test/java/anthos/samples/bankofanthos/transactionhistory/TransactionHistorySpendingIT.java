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
import static org.mockito.Mockito.mock;

import com.auth0.jwt.JWT;
import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.algorithms.Algorithm;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.interfaces.RSAPrivateKey;
import java.security.interfaces.RSAPublicKey;
import java.sql.Timestamp;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.Date;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;
import javax.sql.DataSource;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.MapPropertySource;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.util.ReflectionTestUtils;

/**
 * Integration test for the monthly spending per counterparty against the
 * real ledger database (Postgres with the Bank of Anthos schema).
 *
 * Transactions are stored with chosen timestamps, then the totals are read
 * back through the controller and the grouped repository query. It covers
 * the month boundaries, transfers to oneself, accounts that share a number
 * but not a routing number, and a history much longer than the cached
 * history list.
 *
 * Runs only when SPRING_DATASOURCE_URL, SPRING_DATASOURCE_USERNAME and
 * SPRING_DATASOURCE_PASSWORD are set; the unit test run skips *IT classes.
 *
 * The ledger is append-only, so every test uses freshly generated account
 * numbers instead of cleaning up.
 */
class TransactionHistorySpendingIT {

    private static final String LOCAL_ROUTING_NUM = "883745000";
    private static final String EXTERNAL_ROUTING_NUM = "808889588";
    private static final String FEBRUARY = "2026-02";
    private static final String MARCH = "2026-03";

    private static AnnotationConfigApplicationContext context;
    private static KeyPair keys;
    private static JdbcTemplate jdbc;
    private static TransactionRepository repository;
    private static TransactionHistoryController controller;

    @BeforeAll
    static void setUp() throws Exception {
        KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA");
        generator.initialize(2048);
        keys = generator.generateKeyPair();

        context = new AnnotationConfigApplicationContext();
        context.getEnvironment().getPropertySources().addFirst(
            new MapPropertySource("integration-test", Map.of(
                "LOCAL_ROUTING_NUM", LOCAL_ROUTING_NUM,
                "VERSION", "integration-test",
                "PUB_KEY_PATH", "unused")));
        context.register(LedgerDbTestConfig.class, ServiceTestConfig.class,
            LedgerReaderTestConfig.class, TransactionCache.class,
            TransactionHistoryController.class);
        context.refresh();
        jdbc = new JdbcTemplate(context.getBean(DataSource.class));
        repository = context.getBean(TransactionRepository.class);
        controller = context.getBean(TransactionHistoryController.class);
        // 15 March 2026, noon UTC: the months are March and February 2026.
        ReflectionTestUtils.setField(controller, "clock", Clock.fixed(
            Instant.parse("2026-03-15T12:00:00Z"), ZoneOffset.UTC));
    }

    @AfterAll
    static void tearDown() {
        if (context != null) {
            context.close();
        }
    }

    @Test
    @DisplayName("Transactions on the edges of the months land in the right "
        + "month, and older ones are left out")
    void monthBoundaries() {
        String account = newAccountNum();
        String shop = newAccountNum();
        insert(account, LOCAL_ROUTING_NUM, shop, LOCAL_ROUTING_NUM, 1,
            "2026-01-31 23:59:59");
        insert(account, LOCAL_ROUTING_NUM, shop, LOCAL_ROUTING_NUM, 10,
            "2026-02-01 00:00:00");
        insert(account, LOCAL_ROUTING_NUM, shop, LOCAL_ROUTING_NUM, 100,
            "2026-02-28 23:59:59.999");
        insert(account, LOCAL_ROUTING_NUM, shop, LOCAL_ROUTING_NUM, 1000,
            "2026-03-01 00:00:00");
        insert(account, LOCAL_ROUTING_NUM, shop, LOCAL_ROUTING_NUM, 10000,
            "2026-03-14 08:30:00");

        List<MonthlySpending> result = spending(account);

        assertEquals(2, result.size());
        assertEquals(MARCH, result.get(0).month());
        assertEquals(List.of(new CounterpartySpending(
            shop, LOCAL_ROUTING_NUM, 11000)), result.get(0).counterparties());
        assertEquals(FEBRUARY, result.get(1).month());
        assertEquals(List.of(new CounterpartySpending(
            shop, LOCAL_ROUTING_NUM, 110)), result.get(1).counterparties());
    }

    @Test
    @DisplayName("Totals are per counterparty, largest first, and the same "
        + "account number at another bank is another counterparty")
    void totalsPerCounterparty() {
        String account = newAccountNum();
        String small = newAccountNum();
        String large = newAccountNum();
        insert(account, LOCAL_ROUTING_NUM, small, LOCAL_ROUTING_NUM, 300,
            "2026-03-02 10:00:00");
        insert(account, LOCAL_ROUTING_NUM, large, LOCAL_ROUTING_NUM, 4000,
            "2026-03-03 10:00:00");
        insert(account, LOCAL_ROUTING_NUM, large, LOCAL_ROUTING_NUM, 2000,
            "2026-03-04 10:00:00");
        insert(account, LOCAL_ROUTING_NUM, large, EXTERNAL_ROUTING_NUM, 50,
            "2026-03-05 10:00:00");

        List<MonthlySpending> result = spending(account);

        assertEquals(List.of(
            new CounterpartySpending(large, LOCAL_ROUTING_NUM, 6000),
            new CounterpartySpending(small, LOCAL_ROUTING_NUM, 300),
            new CounterpartySpending(large, EXTERNAL_ROUTING_NUM, 50)),
            result.get(0).counterparties());
        assertEquals(List.of(), result.get(1).counterparties());
    }

    @Test
    @DisplayName("Transfers to oneself, money received, and the outgoing "
        + "transactions of an account with the same number at another "
        + "bank are not counted")
    void selfTransfersAndOtherRowsAreNotCounted() {
        String account = newAccountNum();
        String friend = newAccountNum();
        // To oneself.
        insert(account, LOCAL_ROUTING_NUM, account, LOCAL_ROUTING_NUM, 700,
            "2026-03-02 10:00:00");
        // Received.
        insert(friend, LOCAL_ROUTING_NUM, account, LOCAL_ROUTING_NUM, 800,
            "2026-03-03 10:00:00");
        // Sent by an account with the same number at another bank.
        insert(account, EXTERNAL_ROUTING_NUM, friend, LOCAL_ROUTING_NUM, 900,
            "2026-03-04 10:00:00");
        // Sent to the same number at another bank is spending.
        insert(account, LOCAL_ROUTING_NUM, account, EXTERNAL_ROUTING_NUM, 60,
            "2026-03-05 10:00:00");

        List<MonthlySpending> result = spending(account);

        assertEquals(List.of(new CounterpartySpending(
            account, EXTERNAL_ROUTING_NUM, 60)),
            result.get(0).counterparties());
    }

    @Test
    @DisplayName("An account without transactions has two empty months")
    void accountWithoutTransactions() {
        List<MonthlySpending> result = spending(newAccountNum());

        assertEquals(2, result.size());
        assertEquals(List.of(), result.get(0).counterparties());
        assertEquals(List.of(), result.get(1).counterparties());
    }

    @Test
    @DisplayName("The totals of a history far longer than the cached history "
        + "list are exact")
    void largeHistoryTotalsAreExact() {
        String account = newAccountNum();
        long base = ThreadLocalRandom.current().nextLong(
            2_000_000_000L, 8_000_000_000L);
        // 3 counterparties: 20_000 older rows (amount 1) before the two
        // months, and 1_000 rows (amount 2) in each of the two months.
        generate(account, base, 20_000, 1,
            "TIMESTAMP '2025-06-01 00:00:00' + (g || ' seconds')::interval");
        generate(account, base, 1_000, 2,
            "TIMESTAMP '2026-02-01 00:00:00' + (g || ' seconds')::interval");
        generate(account, base, 1_000, 2,
            "TIMESTAMP '2026-03-01 00:00:00' + (g || ' seconds')::interval");

        List<MonthlySpending> result = spending(account);

        // Rows go to counterparty base + (g % 3) + 1. For g = 1..1000
        // that is 334 rows for base + 2 and 333 rows for each of the
        // others, 2 cents each. Ties are ordered by account number.
        for (MonthlySpending month : result) {
            assertEquals(List.of(
                new CounterpartySpending(
                    String.valueOf(base + 2), LOCAL_ROUTING_NUM, 668),
                new CounterpartySpending(
                    String.valueOf(base + 1), LOCAL_ROUTING_NUM, 666),
                new CounterpartySpending(
                    String.valueOf(base + 3), LOCAL_ROUTING_NUM, 666)),
                month.counterparties());
        }
    }

    @Test
    @DisplayName("The repository query reads from the given time onward")
    void repositoryQueryReadsFromGivenTime() {
        String account = newAccountNum();
        String shop = newAccountNum();
        insert(account, LOCAL_ROUTING_NUM, shop, LOCAL_ROUTING_NUM, 5,
            "2026-02-10 10:00:00");
        insert(account, LOCAL_ROUTING_NUM, shop, LOCAL_ROUTING_NUM, 7,
            "2026-03-10 10:00:00");

        List<Object[]> rows = repository.spendingByCounterparty(
            account, LOCAL_ROUTING_NUM, LocalDateTime.of(2026, 3, 1, 0, 0));

        assertEquals(1, rows.size());
        assertEquals("2026-03", rows.get(0)[0]);
        assertEquals(shop, rows.get(0)[1].toString().trim());
        assertEquals(LOCAL_ROUTING_NUM, rows.get(0)[2].toString().trim());
        assertEquals(7L, ((Number) rows.get(0)[3]).longValue());
    }

    @Test
    @DisplayName("A token for another account is not authorized")
    void otherAccountsSpendingIsRefused() {
        ResponseEntity<?> response = controller.getSpending(
            bearer(newAccountNum()), newAccountNum());

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
    }

    @SuppressWarnings("unchecked")
    private static List<MonthlySpending> spending(String account) {
        ResponseEntity<?> response =
            controller.getSpending(bearer(account), account);
        assertEquals(HttpStatus.OK, response.getStatusCode());
        return (List<MonthlySpending>) response.getBody();
    }

    /**
     * Stores `count` outgoing rows of the account, g = 1..count, to the
     * counterparties base + (g % 3) + 1 at the time given by an SQL
     * expression over g.
     */
    private static void generate(String account, long base, int count,
            int amount, String timestampSql) {
        jdbc.update("INSERT INTO TRANSACTIONS (FROM_ACCT, TO_ACCT, "
            + "FROM_ROUTE, TO_ROUTE, AMOUNT, TIMESTAMP) "
            + "SELECT ?, CAST(? + (g % 3) + 1 AS TEXT), ?, ?, ?, "
            + timestampSql + " FROM generate_series(1, ?) g",
            account, base, LOCAL_ROUTING_NUM, LOCAL_ROUTING_NUM, amount,
            count);
    }

    private static void insert(String fromAcct, String fromRoute,
            String toAcct, String toRoute, int amount, String timestamp) {
        jdbc.update("INSERT INTO TRANSACTIONS (FROM_ACCT, TO_ACCT, "
            + "FROM_ROUTE, TO_ROUTE, AMOUNT, TIMESTAMP) "
            + "VALUES (?, ?, ?, ?, ?, ?)",
            fromAcct, toAcct, fromRoute, toRoute, amount,
            Timestamp.valueOf(timestamp));
    }

    private static String newAccountNum() {
        return String.valueOf(
            ThreadLocalRandom.current().nextLong(1_000_000_000L,
                10_000_000_000L));
    }

    private static String bearer(String account) {
        return "Bearer " + JWT.create()
            .withClaim("acct", account)
            .withExpiresAt(new Date(System.currentTimeMillis() + 60_000))
            .sign(Algorithm.RSA256(null, (RSAPrivateKey) keys.getPrivate()));
    }

    @Configuration
    static class ServiceTestConfig {
        @Bean
        JWTVerifier verifier() {
            return JWT.require(
                Algorithm.RSA256((RSAPublicKey) keys.getPublic(), null))
                .build();
        }

        @Bean
        MeterRegistry meterRegistry() {
            return new SimpleMeterRegistry();
        }
    }

    @Configuration
    static class LedgerReaderTestConfig {
        @Bean
        LedgerReader ledgerReader() {
            // The real reader starts a polling thread that is not needed to
            // read the spending back.
            return mock(LedgerReader.class);
        }
    }
}
