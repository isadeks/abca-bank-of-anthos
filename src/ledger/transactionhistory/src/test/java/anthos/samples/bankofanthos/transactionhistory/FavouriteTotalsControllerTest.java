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
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.interfaces.Claim;
import com.auth0.jwt.interfaces.DecodedJWT;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Date;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

class FavouriteTotalsControllerTest {

    private static final String ACCT = "1234567890";
    private static final String TOKEN = "abc";

    private JWTVerifier verifier;
    private TransactionRepository repo;
    private ContactsClient contacts;
    private FavouriteTotalsController controller;

    private static Claim claim(String value) {
        Claim c = mock(Claim.class);
        when(c.asString()).thenReturn(value);
        return c;
    }

    private static Transaction tx(int amount) throws Exception {
        Transaction t = new Transaction();
        java.lang.reflect.Field f = Transaction.class.getDeclaredField("amount");
        f.setAccessible(true);
        f.set(t, amount);
        return t;
    }

    @BeforeEach
    void setUp() {
        verifier = mock(JWTVerifier.class);
        repo = mock(TransactionRepository.class);
        contacts = mock(ContactsClient.class);
        DecodedJWT jwt = mock(DecodedJWT.class);
        when(verifier.verify(TOKEN)).thenReturn(jwt);
        Claim acctClaim = claim(ACCT);
        Claim userClaim = claim("testuser");
        when(jwt.getClaim("acct")).thenReturn(acctClaim);
        when(jwt.getClaim("user")).thenReturn(userClaim);
        // 2025-02-14 in UTC
        Clock clock = Clock.fixed(Instant.parse("2025-02-14T10:15:30Z"),
            ZoneOffset.UTC);
        controller = new FavouriteTotalsController(verifier, repo, contacts,
            clock);
    }

    @Test
    @DisplayName("The window runs from the first of this month to the first "
        + "of the next, in UTC")
    void dateWindow() {
        assertEquals(Date.from(Instant.parse("2025-02-01T00:00:00Z")),
            controller.monthStart());
        assertEquals(Date.from(Instant.parse("2025-03-01T00:00:00Z")),
            controller.nextMonthStart());
    }

    @Test
    @DisplayName("The window rolls over the year in December")
    void dateWindowDecember() {
        Clock clock = Clock.fixed(Instant.parse("2025-12-31T23:59:59Z"),
            ZoneOffset.UTC);
        FavouriteTotalsController c = new FavouriteTotalsController(verifier,
            repo, contacts, clock);
        assertEquals(Date.from(Instant.parse("2025-12-01T00:00:00Z")),
            c.monthStart());
        assertEquals(Date.from(Instant.parse("2026-01-01T00:00:00Z")),
            c.nextMonthStart());
    }

    @Test
    @DisplayName("Sums the amounts sent to each favourite in the month window")
    void totalsPerFavourite() throws Exception {
        when(contacts.getFavourites("testuser", TOKEN)).thenReturn(List.of(
            Map.of("label", "Alice", "account_num", "1111111111",
                "routing_num", "883745000"),
            Map.of("label", "Bob", "account_num", "2222222222",
                "routing_num", "883745000")));
        Date from = Date.from(Instant.parse("2025-02-01T00:00:00Z"));
        Date to = Date.from(Instant.parse("2025-03-01T00:00:00Z"));
        when(repo.findSentBetween(ACCT, "883745000", "1111111111", from, to))
            .thenReturn(List.of(tx(1000), tx(250)));
        when(repo.findSentBetween(ACCT, "883745000", "2222222222", from, to))
            .thenReturn(List.of());

        ResponseEntity<?> res =
            controller.getFavouriteTotals("Bearer " + TOKEN, ACCT);

        assertEquals(HttpStatus.OK, res.getStatusCode());
        List<?> body = (List<?>) res.getBody();
        assertEquals(2, body.size());
        Map<?, ?> alice = (Map<?, ?>) body.get(0);
        assertEquals("Alice", alice.get("label"));
        assertEquals(1250L, alice.get("totalSent"));
        assertEquals(0L, ((Map<?, ?>) body.get(1)).get("totalSent"));
    }

    @Test
    @DisplayName("A customer without favourites gets an empty list and the "
        + "ledger is not queried")
    void noFavourites() {
        when(contacts.getFavourites("testuser", TOKEN)).thenReturn(List.of());

        ResponseEntity<?> res =
            controller.getFavouriteTotals("Bearer " + TOKEN, ACCT);

        assertEquals(HttpStatus.OK, res.getStatusCode());
        assertEquals(List.of(), res.getBody());
        verify(repo, never()).findSentBetween(any(), any(), any(), any(),
            any());
    }

    @Test
    @DisplayName("Another customer's account is refused")
    void otherAccount() {
        ResponseEntity<?> res =
            controller.getFavouriteTotals("Bearer " + TOKEN, "9876543210");
        assertEquals(HttpStatus.UNAUTHORIZED, res.getStatusCode());
    }

    @Test
    @DisplayName("A non-numeric account id is a bad request")
    void invalidAccount() {
        ResponseEntity<?> res =
            controller.getFavouriteTotals("Bearer " + TOKEN, "abc");
        assertEquals(HttpStatus.BAD_REQUEST, res.getStatusCode());
    }
}
