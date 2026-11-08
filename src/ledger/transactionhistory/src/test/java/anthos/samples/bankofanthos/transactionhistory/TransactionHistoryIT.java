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
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedList;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.MapPropertySource;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

/**
 * Integration test for the transaction history against the real ledger
 * database (Postgres with the Bank of Anthos schema).
 *
 * Transactions are stored the way the ledger writer stores them, then the
 * history is read back through the controller, cache and repository queries.
 *
 * Runs only when SPRING_DATASOURCE_URL, SPRING_DATASOURCE_USERNAME and
 * SPRING_DATASOURCE_PASSWORD are set; the unit test run skips *IT classes.
 *
 * The ledger is append-only, so every test uses freshly generated account
 * numbers instead of cleaning up.
 */
class TransactionHistoryIT {

    private static final String LOCAL_ROUTING_NUM = "883745000";
    private static final String EXTERNAL_ROUTING_NUM = "808889588";

    private static AnnotationConfigApplicationContext context;
    private static KeyPair keys;
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
        repository = context.getBean(TransactionRepository.class);
        controller = context.getBean(TransactionHistoryController.class);
    }

    @AfterAll
    static void tearDown() {
        if (context != null) {
            context.close();
        }
    }

    @Test
    @DisplayName("Transactions written to the ledger show up in the history "
        + "of both accounts, newest first")
    void historyReflectsLedger() throws Exception {
        String external = newAccountNum();
        String alice = newAccountNum();
        String bob = newAccountNum();
        repository.save(transaction(external, EXTERNAL_ROUTING_NUM,
            alice, LOCAL_ROUTING_NUM, 5000));
        // Make sure the two rows get distinct timestamps.
        Thread.sleep(20);
        repository.save(transaction(alice, LOCAL_ROUTING_NUM,
            bob, LOCAL_ROUTING_NUM, 1200));

        ResponseEntity<?> aliceResponse =
            controller.getTransactions(bearer(alice), alice);
        ResponseEntity<?> bobResponse =
            controller.getTransactions(bearer(bob), bob);

        assertEquals(HttpStatus.OK, aliceResponse.getStatusCode());
        ArrayList<Transaction> aliceHistory = new ArrayList<>(
            (Collection<Transaction>) aliceResponse.getBody());
        assertEquals(2, aliceHistory.size());
        assertEquals(1200, aliceHistory.get(0).getAmount());
        assertEquals(alice, aliceHistory.get(0).getFromAccountNum());
        assertEquals(bob, aliceHistory.get(0).getToAccountNum());
        assertEquals(5000, aliceHistory.get(1).getAmount());
        assertEquals(external, aliceHistory.get(1).getFromAccountNum());
        assertEquals(EXTERNAL_ROUTING_NUM,
            aliceHistory.get(1).getFromRoutingNum());
        assertEquals(alice, aliceHistory.get(1).getToAccountNum());

        assertEquals(HttpStatus.OK, bobResponse.getStatusCode());
        ArrayList<Transaction> bobHistory = new ArrayList<>(
            (Collection<Transaction>) bobResponse.getBody());
        assertEquals(1, bobHistory.size());
        assertEquals(1200, bobHistory.get(0).getAmount());
    }

    @Test
    @DisplayName("An account without transactions has an empty history")
    void unknownAccountHasEmptyHistory() {
        String account = newAccountNum();

        ResponseEntity<?> response =
            controller.getTransactions(bearer(account), account);

        assertEquals(HttpStatus.OK, response.getStatusCode());
        assertEquals(0, ((Collection<?>) response.getBody()).size());
    }

    @Test
    @DisplayName("The history query returns the newest transactions first "
        + "and respects the page size")
    void findForAccountIsNewestFirstAndLimited() throws Exception {
        String account = newAccountNum();
        for (int amount = 1; amount <= 3; amount++) {
            repository.save(transaction(newAccountNum(), EXTERNAL_ROUTING_NUM,
                account, LOCAL_ROUTING_NUM, amount));
            Thread.sleep(20);
        }

        LinkedList<Transaction> page = repository.findForAccount(
            account, LOCAL_ROUTING_NUM,
            PageRequest.of(0, 2));

        assertEquals(2, page.size());
        assertEquals(3, page.get(0).getAmount());
        assertEquals(2, page.get(1).getAmount());
    }

    @Test
    @DisplayName("A token for another account is not authorized")
    void otherAccountsHistoryIsRefused() {
        ResponseEntity<?> response = controller.getTransactions(
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
            // The real reader starts a polling thread that is not needed to
            // read the history back.
            return mock(LedgerReader.class);
        }
    }
}
