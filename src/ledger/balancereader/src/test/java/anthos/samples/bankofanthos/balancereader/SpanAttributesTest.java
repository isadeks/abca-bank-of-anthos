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

import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.exceptions.JWTVerificationException;
import com.auth0.jwt.interfaces.Claim;
import com.auth0.jwt.interfaces.DecodedJWT;
import com.google.common.cache.LoadingCache;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.test.util.ReflectionTestUtils;

/**
 * Balance reads tag the current span with the routing number and whether the
 * balance was served from the cache, and never with the account number.
 */
class SpanAttributesTest {

    private static final String ROUTING = "123456789";
    private static final String ACCOUNT = "1234567890";

    private TransactionRepository repo;
    private Tracer tracer;
    private Span span;
    private BalanceReaderController controller;
    private JWTVerifier verifier;

    @BeforeEach
    void setUp() {
        repo = mock(TransactionRepository.class);
        when(repo.findBalance(ACCOUNT, ROUTING)).thenReturn(250L);
        BalanceCache config = new BalanceCache();
        ReflectionTestUtils.setField(config, "dbRepo", repo);
        LoadingCache<String, Long> cache = config.initializeCache(1000, ROUTING);

        verifier = mock(JWTVerifier.class);
        DecodedJWT jwt = mock(DecodedJWT.class);
        Claim claim = mock(Claim.class);
        when(verifier.verify("abc")).thenReturn(jwt);
        when(jwt.getClaim("acct")).thenReturn(claim);
        when(claim.asString()).thenReturn(ACCOUNT);

        tracer = mock(Tracer.class);
        span = mock(Span.class);
        when(tracer.currentSpan()).thenReturn(span);

        controller = new BalanceReaderController(mock(LedgerReader.class),
            verifier, new SimpleMeterRegistry(), cache, ROUTING, "test",
            tracer);
    }

    @Test
    @DisplayName("A read that loads from the database is tagged "
        + "cache_hit=false, then cache_hit=true once cached")
    void cacheHitFlagFollowsTheCache() {
        controller.getBalance("Bearer abc", ACCOUNT);
        verify(span).tag(BalanceReaderController.CACHE_HIT_TAG, false);

        controller.getBalance("Bearer abc", ACCOUNT);
        verify(span).tag(BalanceReaderController.CACHE_HIT_TAG, true);
        verify(span, times(2)).tag(
            BalanceReaderController.ROUTING_NUM_TAG, ROUTING);
    }

    @Test
    @DisplayName("The account number is not put in any span attribute")
    void accountNumberIsNotTagged() {
        controller.getBalance("Bearer abc", ACCOUNT);

        ArgumentCaptor<String> values = ArgumentCaptor.forClass(String.class);
        verify(span).tag(anyString(), values.capture());
        // String-valued tags: only the routing number.
        for (String value : values.getAllValues()) {
            org.junit.jupiter.api.Assertions.assertFalse(
                value != null && value.contains(ACCOUNT),
                "account number found in span attribute: " + value);
        }
        verify(span, never()).tag(anyString(), eq(ACCOUNT));
    }

    @Test
    @DisplayName("An unauthorized read is not tagged")
    void unauthorizedReadIsNotTagged() {
        when(verifier.verify("bad"))
            .thenThrow(new JWTVerificationException("bad"));

        controller.getBalance("Bearer bad", ACCOUNT);

        verify(span, never()).tag(anyString(), anyString());
        verify(span, never()).tag(anyString(), anyBoolean());
    }

    @Test
    @DisplayName("Without an active span a read still succeeds")
    void noActiveSpan() {
        when(tracer.currentSpan()).thenReturn(null);

        org.junit.jupiter.api.Assertions.assertEquals(250L,
            controller.getBalance("Bearer abc", ACCOUNT).getBody());
    }
}
