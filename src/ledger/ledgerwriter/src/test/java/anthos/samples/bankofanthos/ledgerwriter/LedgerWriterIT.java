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
 * Integration test for the ledger writer against the real ledger database
 * (Postgres with the Bank of Anthos schema).
 *
 * Runs only when SPRING_DATASOURCE_URL, SPRING_DATASOURCE_USERNAME and
 * SPRING_DATASOURCE_PASSWORD are set; the unit test run skips *IT classes.
 *
 * The ledger is append-only, so every test uses freshly generated account
 * numbers instead of cleaning up.
 */
class LedgerWriterIT {

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
    @DisplayName("A deposit from an external bank is stored in the ledger")
    void externalDepositIsStored() throws Exception {
        String external = newAccountNum();
        String account = newAccountNum();

        ResponseEntity<?> response = controller.addTransaction(
            bearer(account),
            transaction(external, EXTERNAL_ROUTING_NUM,
                account, LOCAL_ROUTING_NUM, 5000));

        assertEquals(HttpStatus.CREATED, response.getStatusCode());
        List<Map<String, Object>> rows = rowsFor(account);
        assertEquals(1, rows.size());
        Map<String, Object> row = rows.get(0);
        assertEquals(external, row.get("from_acct"));
        assertEquals(EXTERNAL_ROUTING_NUM, row.get("from_route"));
        assertEquals(account, row.get("to_acct"));
        assertEquals(LOCAL_ROUTING_NUM, row.get("to_route"));
        assertEquals(5000, row.get("amount"));
        assertTrue(row.get("timestamp") != null, "timestamp is set");
    }

    @Test
    @DisplayName("An internal transfer the sender can afford is stored "
        + "for both accounts")
    void internalTransferIsStored() throws Exception {
        String sender = newAccountNum();
        String receiver = newAccountNum();

        ResponseEntity<?> response = controller.addTransaction(
            bearer(sender),
            transaction(sender, LOCAL_ROUTING_NUM,
                receiver, LOCAL_ROUTING_NUM, 1200));

        assertEquals(HttpStatus.CREATED, response.getStatusCode());
        assertEquals(1, rowsFor(sender).size());
        assertEquals(1, rowsFor(receiver).size());
        assertEquals(1200, rowsFor(receiver).get(0).get("amount"));
    }

    @Test
    @DisplayName("An internal transfer above the sender's balance "
        + "is rejected and nothing is stored")
    void transferAboveBalanceIsNotStored() throws Exception {
        String sender = newAccountNum();
        String receiver = newAccountNum();

        ResponseEntity<?> response = controller.addTransaction(
            bearer(sender),
            transaction(sender, LOCAL_ROUTING_NUM,
                receiver, LOCAL_ROUTING_NUM,
                Integer.parseInt(BALANCE_OF_SENDER) + 1));

        assertEquals(HttpStatus.BAD_REQUEST, response.getStatusCode());
        assertEquals(0, rowsFor(sender).size());
        assertEquals(0, rowsFor(receiver).size());
    }

    private static List<Map<String, Object>> rowsFor(String account) {
        return jdbc.queryForList(
            "SELECT from_acct, from_route, to_acct, to_route, amount, "
                + "timestamp FROM transactions "
                + "WHERE from_acct = ? OR to_acct = ?",
            account, account);
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
            String toAcct, String toRoute, int amount) throws Exception {
        String json = String.format(
            "{\"fromAccountNum\":\"%s\",\"fromRoutingNum\":\"%s\","
                + "\"toAccountNum\":\"%s\",\"toRoutingNum\":\"%s\","
                + "\"amount\":%d,\"uuid\":\"%s\"}",
            fromAcct, fromRoute, toAcct, toRoute, amount, UUID.randomUUID());
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
