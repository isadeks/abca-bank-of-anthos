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
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.interfaces.Claim;
import com.auth0.jwt.interfaces.DecodedJWT;
import com.google.common.cache.LoadingCache;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.util.ReflectionTestUtils;

/**
 * Regression tests for slow balance reads: a balance read must be served from
 * the cache (kept current by the ledger poller) and a cache miss must be loaded
 * with the aggregate balance query, never by scanning the whole ledger.
 */
class BalanceReadCachingTest {

    private static final String ROUTING = "123456789";
    private static final String ACCOUNT = "1234567890";

    private TransactionRepository repo;
    private LoadingCache<String, Long> cache;
    private BalanceReaderController controller;

    @BeforeEach
    void setUp() {
        repo = mock(TransactionRepository.class);
        BalanceCache config = new BalanceCache();
        ReflectionTestUtils.setField(config, "dbRepo", repo);
        cache = config.initializeCache(1000, ROUTING);

        JWTVerifier verifier = mock(JWTVerifier.class);
        DecodedJWT jwt = mock(DecodedJWT.class);
        Claim claim = mock(Claim.class);
        when(verifier.verify("abc")).thenReturn(jwt);
        when(jwt.getClaim("acct")).thenReturn(claim);
        when(claim.asString()).thenReturn(ACCOUNT);

        controller = new BalanceReaderController(mock(LedgerReader.class),
            verifier, new SimpleMeterRegistry(), cache, ROUTING, "test");
    }

    @Test
    @DisplayName("A cache miss loads the balance with the aggregate query "
        + "and does not scan the ledger")
    void cacheMissUsesAggregateQuery() {
        when(repo.findBalance(ACCOUNT, ROUTING)).thenReturn(250L);

        ResponseEntity<?> response =
            controller.getBalance("Bearer abc", ACCOUNT);

        assertEquals(HttpStatus.OK, response.getStatusCode());
        assertEquals(250L, response.getBody());
        verify(repo, never()).findLatest(anyLong());
    }

    @Test
    @DisplayName("An account without transactions has a balance of 0")
    void missingBalanceIsZero() {
        when(repo.findBalance(ACCOUNT, ROUTING)).thenReturn(null);

        ResponseEntity<?> response =
            controller.getBalance("Bearer abc", ACCOUNT);

        assertEquals(0L, response.getBody());
    }

    @Test
    @DisplayName("Repeated reads are served from the cache, "
        + "hitting the database once")
    void repeatedReadsHitTheDatabaseOnce() {
        when(repo.findBalance(ACCOUNT, ROUTING)).thenReturn(250L);

        for (int i = 0; i < 5; i++) {
            ResponseEntity<?> response =
                controller.getBalance("Bearer abc", ACCOUNT);
            assertEquals(250L, response.getBody());
        }

        verify(repo, times(1)).findBalance(anyString(), anyString());
        verify(repo, never()).findLatest(anyLong());
    }

    @Test
    @DisplayName("A cached balance updated by the poller is what is served")
    void cachedBalanceUpdatedByPollerIsServed() {
        when(repo.findBalance(ACCOUNT, ROUTING)).thenReturn(250L);
        controller.getBalance("Bearer abc", ACCOUNT);

        // The ledger poller applies a new deposit to the cached entry.
        cache.put(ACCOUNT, 300L);

        ResponseEntity<?> response =
            controller.getBalance("Bearer abc", ACCOUNT);
        assertEquals(300L, response.getBody());
        verify(repo, times(1)).findBalance(anyString(), anyString());
    }
}
