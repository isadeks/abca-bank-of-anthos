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

package anthos.samples.bankofanthos.ledgerwriter;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.auth0.jwt.JWT;
import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.algorithms.Algorithm;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import io.micrometer.core.instrument.Clock;
import io.micrometer.core.lang.Nullable;
import io.micrometer.stackdriver.StackdriverConfig;
import io.micrometer.stackdriver.StackdriverMeterRegistry;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.interfaces.RSAPrivateKey;
import java.security.interfaces.RSAPublicKey;
import java.util.Date;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.client.RestTemplate;

/**
 * Category integration test for the ledger writer against the real ledger database
 * (Postgres with the Bank of Anthos schema).
 *
 * Runs only when SPRING_DATASOURCE_URL, SPRING_DATASOURCE_USERNAME and
 * SPRING_DATASOURCE_PASSWORD are set; the unit test run skips *IT classes.
 *
 * The ledger is append-only, so every test uses freshly generated account
 * numbers instead of cleaning up.
 */
class LedgerWriterCategoryIT {

    private static final String LOCAL_ROUTING_NUM = "883745000";
    private static final String EXTERNAL_ROUTING_NUM = "808889588";
    private static final String BALANCE_OF_SENDER = "5000";

    private static AnnotationConfigApplicationContext context;
    private static JdbcTemplate jdbc;
    private static HttpServer balanceStub;
    private static KeyPair keys;
    private static LedgerWriterController controller;

    @BeforeAll
    static void setUp() throws Exception {
        context = new AnnotationConfigApplicationContext(
            LedgerDbTestConfig.class);
        jdbc = new JdbcTemplate(context.getBean(javax.sql.DataSource.class));

        KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA");
        generator.initialize(2048);
        keys = generator.generateKeyPair();
        JWTVerifier verifier = JWT.require(
            Algorithm.RSA256((RSAPublicKey) keys.getPublic(), null)).build();

        // Stands in for the balance reader, which the ledger writer asks
        // for the sender's balance before accepting an internal transfer.
        balanceStub = HttpServer.create(new InetSocketAddress("localhost", 0), 0);
        balanceStub.createContext("/balances/", exchange -> {
            byte[] body = BALANCE_OF_SENDER.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        balanceStub.start();

        controller = new LedgerWriterController(
            verifier,
            disabledMeterRegistry(),
            context.getBean(TransactionRepository.class),
            new TransactionValidator(),
            LOCAL_ROUTING_NUM,
            "http://localhost:" + balanceStub.getAddress().getPort()
                + "/balances",
            "integration-test");
        controller.restTemplate = new RestTemplate();
    }

    @AfterAll
    static void tearDown() {
        if (balanceStub != null) {
            balanceStub.stop(0);
        }
        if (context != null) {
            context.close();
        }
    }

    @Test
    @DisplayName("The category is stored; missing or unknown is Other")
    void categoryIsStored() throws Exception {
        String sender = newAccountNum();
        String receiver = newAccountNum();
        String[] sent = {"Groceries", "Eating out", null, "Bogus"};
        String[] expected = {"Groceries", "Eating out", "Other", "Other"};
        for (String category : sent) {
            ResponseEntity<?> response = controller.addTransaction(
                bearer(sender),
                transaction(sender, LOCAL_ROUTING_NUM,
                    receiver, LOCAL_ROUTING_NUM, 100, category));
            assertEquals(HttpStatus.CREATED, response.getStatusCode());
        }
        List<Map<String, Object>> rows = jdbc.queryForList(
            "SELECT category FROM transactions WHERE from_acct = ? "
                + "ORDER BY transaction_id", sender);
        assertEquals(4, rows.size());
        for (int i = 0; i < expected.length; i++) {
            assertEquals(expected[i], rows.get(i).get("category"));
        }
    }

    @Test
    @DisplayName("A row inserted without a category reads back as Other")
    void legacyRowDefaultsToOther() {
        String account = newAccountNum();
        jdbc.update("INSERT INTO transactions (from_acct, to_acct, "
            + "from_route, to_route, amount, timestamp) "
            + "VALUES (?, ?, ?, ?, 1, now())",
            account, newAccountNum(), LOCAL_ROUTING_NUM, LOCAL_ROUTING_NUM);
        assertEquals("Other", jdbc.queryForObject(
            "SELECT category FROM transactions WHERE from_acct = ?",
            String.class, account));
    }

    private static String newAccountNum() {
        return String.valueOf(
            ThreadLocalRandom.current().nextLong(1_000_000_000L,
                10_000_000_000L));
    }

    private static String bearer(String account) {
        return "Bearer " + JWT.create()
            .withClaim(LedgerWriterController.JWT_ACCOUNT_KEY, account)
            .withExpiresAt(new Date(System.currentTimeMillis() + 60_000))
            .sign(Algorithm.RSA256(null, (RSAPrivateKey) keys.getPrivate()));
    }

    private static Transaction transaction(String fromAcct, String fromRoute,
            String toAcct, String toRoute, int amount, String category)
            throws Exception {
        String categoryJson = category == null
            ? "" : ",\"category\":\"" + category + "\"";
        String json = String.format(
            "{\"fromAccountNum\":\"%s\",\"fromRoutingNum\":\"%s\","
                + "\"toAccountNum\":\"%s\",\"toRoutingNum\":\"%s\","
                + "\"amount\":%d,\"uuid\":\"%s\"%s}",
            fromAcct, fromRoute, toAcct, toRoute, amount, UUID.randomUUID(),
            categoryJson);
        return new ObjectMapper().readValue(json, Transaction.class);
    }

    private static StackdriverMeterRegistry disabledMeterRegistry() {
        return new StackdriverMeterRegistry(new StackdriverConfig() {
            @Override
            public boolean enabled() {
                return false;
            }

            @Override
            public String projectId() {
                return "test";
            }

            @Override
            @Nullable
            public String get(String key) {
                return null;
            }
        }, Clock.SYSTEM);
    }
}
