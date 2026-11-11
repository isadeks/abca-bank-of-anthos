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
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.exceptions.JWTVerificationException;
import com.auth0.jwt.interfaces.Claim;
import com.auth0.jwt.interfaces.DecodedJWT;
import com.google.common.cache.CacheStats;
import com.google.common.cache.LoadingCache;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.Deque;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.util.ReflectionTestUtils;

/**
 * Tests of /spending/{accountId}: the same token and account id checks as
 * /transactions/{accountId}, and the monthly totals built from the rows of
 * the grouped ledger query.
 */
class TransactionHistorySpendingTest {

    private static final String LOCAL_ROUTING_NUM = "123456789";
    private static final String AUTHED_ACCOUNT_NUM = "1234567890";
    private static final String NON_AUTHED_ACCOUNT_NUM = "9876543210";
    private static final String BEARER_TOKEN = "Bearer abc";
    private static final String TOKEN = "abc";

    private TransactionHistoryController controller;
    private TransactionRepository repository;
    private JWTVerifier verifier;
    private Claim claim;

    @SuppressWarnings("unchecked")
    @BeforeEach
    void setUp() {
        LoadingCache<String, Deque<Transaction>> cache =
            mock(LoadingCache.class);
        when(cache.stats()).thenReturn(new CacheStats(0, 0, 0, 0, 0, 0));
        verifier = mock(JWTVerifier.class);
        DecodedJWT jwt = mock(DecodedJWT.class);
        claim = mock(Claim.class);
        when(verifier.verify(TOKEN)).thenReturn(jwt);
        when(jwt.getClaim("acct")).thenReturn(claim);
        when(claim.asString()).thenReturn(AUTHED_ACCOUNT_NUM);
        controller = new TransactionHistoryController(
            mock(LedgerReader.class), new SimpleMeterRegistry(), verifier,
            "path/", cache, LOCAL_ROUTING_NUM, "v0.2.0");
        repository = mock(TransactionRepository.class);
        ReflectionTestUtils.setField(controller, "dbRepo", repository);
        // 15 March 2026, noon UTC.
        ReflectionTestUtils.setField(controller, "clock", Clock.fixed(
            Instant.parse("2026-03-15T12:00:00Z"), ZoneOffset.UTC));
    }

    private static Object[] row(String month, String account, String route,
                                long total) {
        return new Object[] {month, account, route, total};
    }

    @SuppressWarnings("unchecked")
    private List<MonthlySpending> spendingOf(ResponseEntity<?> response) {
        assertEquals(HttpStatus.OK, response.getStatusCode());
        return (List<MonthlySpending>) response.getBody();
    }

    @ParameterizedTest
    @ValueSource(strings = {"abc", "12ab34", "-123", "12.5", "1 2"})
    @DisplayName("Given a non-numeric account id, return 400 without "
        + "querying the ledger")
    void spendingFailsWhenAccountIdIsNotNumeric(String accountId) {
        final ResponseEntity<?> result =
            controller.getSpending(BEARER_TOKEN, accountId);

        assertEquals(HttpStatus.BAD_REQUEST, result.getStatusCode());
        assertEquals("invalid account id", result.getBody());
        verify(repository, never()).spendingByCounterparty(
            anyString(), anyString(), any());
    }

    @Test
    @DisplayName("Given a token for another account, return 401 without "
        + "querying the ledger")
    void spendingFailsWhenAccountDoesNotMatchAuthenticatedUser() {
        final ResponseEntity<?> result =
            controller.getSpending(BEARER_TOKEN, NON_AUTHED_ACCOUNT_NUM);

        assertEquals(HttpStatus.UNAUTHORIZED, result.getStatusCode());
        verify(repository, never()).spendingByCounterparty(
            anyString(), anyString(), any());
    }

    @Test
    @DisplayName("Given the user is not authenticated, return 401")
    void spendingFailsWhenUserNotAuthenticated() {
        when(verifier.verify(TOKEN)).thenThrow(JWTVerificationException.class);

        final ResponseEntity<?> result =
            controller.getSpending(BEARER_TOKEN, AUTHED_ACCOUNT_NUM);

        assertEquals(HttpStatus.UNAUTHORIZED, result.getStatusCode());
    }

    @Test
    @DisplayName("The ledger is queried for the account and local routing "
        + "number from the start of the previous month")
    void spendingQueriesFromStartOfPreviousMonth() {
        controller.getSpending(BEARER_TOKEN, AUTHED_ACCOUNT_NUM);

        verify(repository).spendingByCounterparty(AUTHED_ACCOUNT_NUM,
            LOCAL_ROUTING_NUM, LocalDateTime.of(2026, 2, 1, 0, 0));
    }

    @Test
    @DisplayName("The previous month of January is December of last year")
    void spendingPreviousMonthCrossesYearBoundary() {
        ReflectionTestUtils.setField(controller, "clock", Clock.fixed(
            Instant.parse("2026-01-01T00:00:00Z"), ZoneOffset.UTC));

        List<MonthlySpending> result = spendingOf(
            controller.getSpending(BEARER_TOKEN, AUTHED_ACCOUNT_NUM));

        verify(repository).spendingByCounterparty(AUTHED_ACCOUNT_NUM,
            LOCAL_ROUTING_NUM, LocalDateTime.of(2025, 12, 1, 0, 0));
        assertEquals("2026-01", result.get(0).month());
        assertEquals("2025-12", result.get(1).month());
    }

    @Test
    @DisplayName("Without outgoing transactions both months are returned "
        + "empty")
    void spendingIsEmptyWithoutTransactions() {
        when(repository.spendingByCounterparty(any(), any(), any()))
            .thenReturn(List.of());

        List<MonthlySpending> result = spendingOf(
            controller.getSpending(BEARER_TOKEN, AUTHED_ACCOUNT_NUM));

        assertEquals(2, result.size());
        assertEquals("2026-03", result.get(0).month());
        assertEquals(List.of(), result.get(0).counterparties());
        assertEquals("2026-02", result.get(1).month());
        assertEquals(List.of(), result.get(1).counterparties());
    }

    @Test
    @DisplayName("Rows are grouped by month, largest total first, with "
        + "account numbers trimmed of padding")
    void spendingGroupsRowsByMonth() {
        when(repository.spendingByCounterparty(any(), any(), any()))
            .thenReturn(List.of(
                row("2026-02", "1111111111", "883745000", 500),
                row("2026-03", "2222222222", "883745000", 700),
                row("2026-03", "3333333333", "808889588", 9000000000L),
                row("2026-03", "44444     ", "883745000", 700),
                row("2026-02", "3333333333", "808889588", 900)));

        List<MonthlySpending> result = spendingOf(
            controller.getSpending(BEARER_TOKEN, AUTHED_ACCOUNT_NUM));

        assertEquals(2, result.size());
        assertEquals("2026-03", result.get(0).month());
        assertEquals(List.of(
            new CounterpartySpending("3333333333", "808889588", 9000000000L),
            new CounterpartySpending("2222222222", "883745000", 700),
            new CounterpartySpending("44444", "883745000", 700)),
            result.get(0).counterparties());
        assertEquals("2026-02", result.get(1).month());
        assertEquals(List.of(
            new CounterpartySpending("3333333333", "808889588", 900),
            new CounterpartySpending("1111111111", "883745000", 500)),
            result.get(1).counterparties());
    }

    @Test
    @DisplayName("Rows of months outside the two reported months are ignored")
    void spendingIgnoresOtherMonths() {
        when(repository.spendingByCounterparty(any(), any(), any()))
            .thenReturn(List.of(
                row("2026-01", "1111111111", "883745000", 500),
                row("2026-04", "2222222222", "883745000", 700)));

        List<MonthlySpending> result = spendingOf(
            controller.getSpending(BEARER_TOKEN, AUTHED_ACCOUNT_NUM));

        assertEquals(List.of(), result.get(0).counterparties());
        assertEquals(List.of(), result.get(1).counterparties());
    }

    @Test
    @DisplayName("Given the database fails, return 500")
    void spendingFailsWhenDatabaseThrowsError() {
        when(repository.spendingByCounterparty(any(), any(), any()))
            .thenThrow(new DataAccessResourceFailureException("down"));

        final ResponseEntity<?> result =
            controller.getSpending(BEARER_TOKEN, AUTHED_ACCOUNT_NUM);

        assertNotNull(result);
        assertEquals(HttpStatus.INTERNAL_SERVER_ERROR, result.getStatusCode());
    }
}
