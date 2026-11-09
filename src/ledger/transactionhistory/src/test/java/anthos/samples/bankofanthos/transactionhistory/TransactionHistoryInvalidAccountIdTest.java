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

package anthos.samples.bankofanthos.transactionhistory;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.interfaces.Claim;
import com.auth0.jwt.interfaces.DecodedJWT;
import com.google.common.cache.CacheStats;
import com.google.common.cache.LoadingCache;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.util.Deque;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

/**
 * Tests that /transactions/{accountId} rejects non-numeric account ids with
 * a 400 instead of failing with a 500.
 */
class TransactionHistoryInvalidAccountIdTest {

    private static final String BEARER_TOKEN = "Bearer abc";
    private static final String TOKEN = "abc";

    private TransactionHistoryController controller;
    private LoadingCache<String, Deque<Transaction>> cache;

    @SuppressWarnings("unchecked")
    @BeforeEach
    void setUp() {
        cache = mock(LoadingCache.class);
        when(cache.stats()).thenReturn(new CacheStats(0, 0, 0, 0, 0, 0));
        JWTVerifier verifier = mock(JWTVerifier.class);
        DecodedJWT jwt = mock(DecodedJWT.class);
        Claim claim = mock(Claim.class);
        when(verifier.verify(TOKEN)).thenReturn(jwt);
        when(jwt.getClaim("acct")).thenReturn(claim);
        controller = new TransactionHistoryController(
            mock(LedgerReader.class), new SimpleMeterRegistry(), verifier,
            "path/", cache, "123456789", "v0.2.0");
    }

    @ParameterizedTest
    @ValueSource(strings = {"abc", "12ab34", "-123", "12.5", "1 2", "1234567890x"})
    @DisplayName("Given a non-numeric account id, return 400 without touching the cache")
    void getTransactionsFailsWhenAccountIdIsNotNumeric(String accountId)
            throws Exception {
        // When
        final ResponseEntity<?> actualResult =
            controller.getTransactions(BEARER_TOKEN, accountId);

        // Then
        assertNotNull(actualResult);
        assertEquals(HttpStatus.BAD_REQUEST, actualResult.getStatusCode());
        assertEquals("invalid account id", actualResult.getBody());
        verify(cache, never()).get(anyString());
    }
}
