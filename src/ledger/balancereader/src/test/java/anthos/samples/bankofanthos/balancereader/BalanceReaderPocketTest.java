/*
 * Copyright 2020, Google LLC.
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
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.exceptions.JWTVerificationException;
import com.auth0.jwt.interfaces.Claim;
import com.auth0.jwt.interfaces.DecodedJWT;
import com.google.common.cache.CacheStats;
import com.google.common.cache.LoadingCache;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.util.ReflectionTestUtils;

/**
 * Reading the balance of an account under a given routing number, which is
 * how the frontend reads a customer's Savings pocket.
 */
class BalanceReaderPocketTest {

    private static final String LOCAL_ROUTING_NUM = "123456789";
    private static final String SAVINGS_ROUTING_NUM = "123456999";
    private static final String OTHER_ROUTING_NUM = "987654321";
    private static final String AUTHED_ACCOUNT_NUM = "1234567890";
    private static final String OTHER_ACCOUNT_NUM = "9876543210";
    private static final String BEARER_TOKEN = "Bearer abc";
    private static final String TOKEN = "abc";

    private BalanceReaderController controller;
    private TransactionRepository dbRepo;
    private LoadingCache<String, Long> cache;
    private JWTVerifier verifier;

    @SuppressWarnings("unchecked")
    @BeforeEach
    void setUp() throws Exception {
        verifier = mock(JWTVerifier.class);
        DecodedJWT jwt = mock(DecodedJWT.class);
        Claim claim = mock(Claim.class);
        cache = mock(LoadingCache.class);
        dbRepo = mock(TransactionRepository.class);
        when(cache.stats()).thenReturn(mock(CacheStats.class));
        when(verifier.verify(TOKEN)).thenReturn(jwt);
        when(jwt.getClaim("acct")).thenReturn(claim);
        when(claim.asString()).thenReturn(AUTHED_ACCOUNT_NUM);

        controller = new BalanceReaderController(mock(LedgerReader.class),
            verifier, new SimpleMeterRegistry(), cache, LOCAL_ROUTING_NUM,
            "v0");
        ReflectionTestUtils.setField(controller, "dbRepo", dbRepo);
        ReflectionTestUtils.setField(
            controller, "savingsRoutingNum", SAVINGS_ROUTING_NUM);
    }

    @Test
    @DisplayName("Given the savings routing number, return the pocket balance "
        + "summed from the ledger")
    void pocketBalanceIsReadFromTheLedger() {
        when(dbRepo.findBalance(AUTHED_ACCOUNT_NUM, SAVINGS_ROUTING_NUM))
            .thenReturn(2500L);

        ResponseEntity<?> result = controller.getBalanceForRouting(
            BEARER_TOKEN, AUTHED_ACCOUNT_NUM, SAVINGS_ROUTING_NUM);

        assertEquals(HttpStatus.OK, result.getStatusCode());
        assertEquals(2500L, result.getBody());
    }

    @Test
    @DisplayName("Given a pocket with no transactions, return a zero balance")
    void emptyPocketIsZero() {
        when(dbRepo.findBalance(AUTHED_ACCOUNT_NUM, SAVINGS_ROUTING_NUM))
            .thenReturn(null);

        ResponseEntity<?> result = controller.getBalanceForRouting(
            BEARER_TOKEN, AUTHED_ACCOUNT_NUM, SAVINGS_ROUTING_NUM);

        assertEquals(HttpStatus.OK, result.getStatusCode());
        assertEquals(0L, result.getBody());
    }

    @Test
    @DisplayName("Given the local routing number, return the cached main "
        + "balance")
    void localRoutingUsesTheCache() throws Exception {
        when(cache.get(AUTHED_ACCOUNT_NUM)).thenReturn(100L);

        ResponseEntity<?> result = controller.getBalanceForRouting(
            BEARER_TOKEN, AUTHED_ACCOUNT_NUM, LOCAL_ROUTING_NUM);

        assertEquals(HttpStatus.OK, result.getStatusCode());
        assertEquals(100L, result.getBody());
        verifyNoInteractions(dbRepo);
    }

    @Test
    @DisplayName("Given another user's account, return HTTP Status 401 and "
        + "do not read the pocket")
    void otherUsersPocketIsNotReadable() {
        ResponseEntity<?> result = controller.getBalanceForRouting(
            BEARER_TOKEN, OTHER_ACCOUNT_NUM, SAVINGS_ROUTING_NUM);

        assertEquals(HttpStatus.UNAUTHORIZED, result.getStatusCode());
        assertEquals("not authorized", result.getBody());
        verify(dbRepo, never()).findBalance(anyString(), anyString());
    }

    @Test
    @DisplayName("Given an invalid token, return HTTP Status 401")
    void invalidTokenIsRejected() {
        when(verifier.verify("bad")).thenThrow(
            new JWTVerificationException("bad token"));

        ResponseEntity<?> result = controller.getBalanceForRouting(
            "Bearer bad", AUTHED_ACCOUNT_NUM, SAVINGS_ROUTING_NUM);

        assertEquals(HttpStatus.UNAUTHORIZED, result.getStatusCode());
    }

    @Test
    @DisplayName("Given a routing number that is neither local nor savings, "
        + "return HTTP Status 400")
    void otherRoutingNumbersAreRejected() {
        ResponseEntity<?> result = controller.getBalanceForRouting(
            BEARER_TOKEN, AUTHED_ACCOUNT_NUM, OTHER_ROUTING_NUM);

        assertEquals(HttpStatus.BAD_REQUEST, result.getStatusCode());
        verify(dbRepo, never()).findBalance(anyString(), anyString());
    }

    @Test
    @DisplayName("Given no savings routing number is configured, the savings "
        + "routing number is rejected")
    void pocketsDisabledWhenNotConfigured() {
        ReflectionTestUtils.setField(controller, "savingsRoutingNum", "");

        ResponseEntity<?> result = controller.getBalanceForRouting(
            BEARER_TOKEN, AUTHED_ACCOUNT_NUM, SAVINGS_ROUTING_NUM);

        assertEquals(HttpStatus.BAD_REQUEST, result.getStatusCode());
    }

    @Test
    @DisplayName("Given the ledger database is down, return HTTP Status 500")
    void databaseErrorIsReported() {
        when(dbRepo.findBalance(AUTHED_ACCOUNT_NUM, SAVINGS_ROUTING_NUM))
            .thenThrow(new DataAccessResourceFailureException("down"));

        ResponseEntity<?> result = controller.getBalanceForRouting(
            BEARER_TOKEN, AUTHED_ACCOUNT_NUM, SAVINGS_ROUTING_NUM);

        assertEquals(HttpStatus.INTERNAL_SERVER_ERROR, result.getStatusCode());
    }
}
