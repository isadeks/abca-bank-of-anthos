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

package anthos.samples.bankofanthos.balancereader;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;

import com.auth0.jwt.JWT;
import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.algorithms.Algorithm;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.micrometer.core.instrument.Clock;
import io.micrometer.core.lang.Nullable;
import io.micrometer.stackdriver.StackdriverConfig;
import io.micrometer.stackdriver.StackdriverMeterRegistry;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.interfaces.RSAPrivateKey;
import java.security.interfaces.RSAPublicKey;
import java.util.Date;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;
import java.util.List;
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

/**
 * Integration test for the balance reader against the real ledger database
 * (Postgres with the Bank of Anthos schema).
 *
 * Transactions are stored the way the ledger writer stores them, then the
 * balance is read back through the controller, cache and repository queries.
 *
 * Runs only when SPRING_DATASOURCE_URL, SPRING_DATASOURCE_USERNAME and
 * SPRING_DATASOURCE_PASSWORD are set; the unit test run skips *IT classes.
 *
 * The ledger is append-only, so every test uses freshly generated account
 * numbers instead of cleaning up.
 */
class BalanceReaderIT {

    private static final String LOCAL_ROUTING_NUM = "883745000";
    private static final String EXTERNAL_ROUTING_NUM = "808889588";

    private static AnnotationConfigApplicationContext context;
    private static KeyPair keys;
    private static TransactionRepository repository;
    private static BalanceReaderController controller;

    @BeforeAll
    static void setUp() throws Exception {
        KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA");
        generator.initialize(2048);
        keys = generator.generateKeyPair();

        context = new AnnotationConfigApplicationContext();
        context.getEnvironment().getPropertySources().addFirst(
            new MapPropertySource("integration-test", Map.of(
                "LOCAL_ROUTING_NUM", LOCAL_ROUTING_NUM,
                "VERSION", "integration-test")));
        context.register(LedgerDbTestConfig.class, ServiceTestConfig.class,
            LedgerReaderTestConfig.class, BalanceCache.class, BalanceReaderController.class);
        context.refresh();
        repository = context.getBean(TransactionRepository.class);
        controller = context.getBean(BalanceReaderController.class);
    }

    @AfterAll
    static void tearDown() {
        if (context != null) {
            context.close();
        }
    }

    @Test
    @DisplayName("Deposits and transfers written to the ledger add up "
        + "in the account balance")
    void balanceReflectsLedger() throws Exception {
        String external = newAccountNum();
        String alice = newAccountNum();
        String bob = newAccountNum();
        repository.save(transaction(external, EXTERNAL_ROUTING_NUM,
            alice, LOCAL_ROUTING_NUM, 5000));
        repository.save(transaction(alice, LOCAL_ROUTING_NUM,
            bob, LOCAL_ROUTING_NUM, 1200));

        ResponseEntity<?> aliceBalance =
            controller.getBalance(bearer(alice), alice);
        ResponseEntity<?> bobBalance =
            controller.getBalance(bearer(bob), bob);

        assertEquals(HttpStatus.OK, aliceBalance.getStatusCode());
        assertEquals(3800L, aliceBalance.getBody());
        assertEquals(HttpStatus.OK, bobBalance.getStatusCode());
        assertEquals(1200L, bobBalance.getBody());
    }

    @Test
    @DisplayName("An account without transactions has a balance of zero")
    void unknownAccountHasZeroBalance() {
        String account = newAccountNum();

        ResponseEntity<?> response =
            controller.getBalance(bearer(account), account);

        assertEquals(HttpStatus.OK, response.getStatusCode());
        assertEquals(0L, response.getBody());
    }

    @Test
    @DisplayName("The balance query nets money in against money out")
    void findBalanceNetsIncomingAndOutgoing() throws Exception {
        String external = newAccountNum();
        String account = newAccountNum();
        String other = newAccountNum();
        repository.save(transaction(external, EXTERNAL_ROUTING_NUM,
            account, LOCAL_ROUTING_NUM, 700));
        repository.save(transaction(account, LOCAL_ROUTING_NUM,
            other, LOCAL_ROUTING_NUM, 250));

        assertEquals(450L,
            repository.findBalance(account, LOCAL_ROUTING_NUM));
        // Nothing was received at the external routing number.
        assertNull(repository.findBalance(account, EXTERNAL_ROUTING_NUM));
    }

    @Test
    @DisplayName("The ledger reader's queries see a newly written transaction")
    void newTransactionIsVisibleToTheLedgerReader() throws Exception {
        Long before = repository.latestTransactionId();
        long start = before == null ? -1 : before;
        String account = newAccountNum();
        repository.save(transaction(newAccountNum(), EXTERNAL_ROUTING_NUM,
            account, LOCAL_ROUTING_NUM, 42));

        Long after = repository.latestTransactionId();
        List<Transaction> latest = repository.findLatest(start);

        assertTrue(after != null && after > start);
        assertEquals(1, latest.size());
        assertEquals(account, latest.get(0).getToAccountNum());
        assertEquals(42, latest.get(0).getAmount());
    }

    @Test
    @DisplayName("A token for another account is not authorized")
    void otherAccountsBalanceIsRefused() {
        ResponseEntity<?> response = controller.getBalance(
            bearer(newAccountNum()), newAccountNum());

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
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

    private static Transaction transaction(String fromAcct, String fromRoute,
            String toAcct, String toRoute, int amount) throws Exception {
        String json = String.format(
            "{\"fromAccountNum\":\"%s\",\"fromRoutingNum\":\"%s\","
                + "\"toAccountNum\":\"%s\",\"toRoutingNum\":\"%s\","
                + "\"amount\":%d}",
            fromAcct, fromRoute, toAcct, toRoute, amount);
        return new ObjectMapper().readValue(json, Transaction.class);
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
        StackdriverMeterRegistry meterRegistry() {
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

    @Configuration
    static class LedgerReaderTestConfig {
        @Bean
        LedgerReader ledgerReader() {
            // The real reader starts a polling thread; its queries are
            // exercised directly in this test instead.
            return mock(LedgerReader.class);
        }
    }
}
