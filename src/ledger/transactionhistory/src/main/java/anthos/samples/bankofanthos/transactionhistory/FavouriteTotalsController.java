/*
 * Copyright 2025, Google LLC.
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

import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.exceptions.JWTVerificationException;
import com.auth0.jwt.interfaces.DecodedJWT;
import java.time.Clock;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClientException;

/**
 * Total sent to each favourite contact in the current month (UTC).
 */
@RestController
public final class FavouriteTotalsController {

    private static final Logger LOGGER =
        LogManager.getLogger(FavouriteTotalsController.class);
    private final JWTVerifier verifier;
    private final TransactionRepository dbRepo;
    private final ContactsClient contacts;
    private final Clock clock;

    /**
     * Constructor used by Spring.
     *
     * @param verifier JWT verifier
     * @param dbRepo   ledger repository
     * @param contacts client of the contacts service
     */
    @Autowired
    public FavouriteTotalsController(final JWTVerifier verifier,
            final TransactionRepository dbRepo,
            final ContactsClient contacts) {
        this(verifier, dbRepo, contacts, Clock.systemUTC());
    }

    FavouriteTotalsController(final JWTVerifier verifier,
            final TransactionRepository dbRepo,
            final ContactsClient contacts, final Clock clock) {
        this.verifier = verifier;
        this.dbRepo = dbRepo;
        this.contacts = contacts;
        this.clock = clock;
    }

    /**
     * Start of the current month (UTC), inclusive.
     *
     * @return first instant of this month
     */
    Date monthStart() {
        LocalDate today = LocalDate.now(clock.withZone(ZoneOffset.UTC));
        return Date.from(today.withDayOfMonth(1)
            .atStartOfDay(ZoneOffset.UTC).toInstant());
    }

    /**
     * Start of the next month (UTC), exclusive end of the window.
     *
     * @return first instant of next month
     */
    Date nextMonthStart() {
        LocalDate today = LocalDate.now(clock.withZone(ZoneOffset.UTC));
        return Date.from(today.withDayOfMonth(1).plusMonths(1)
            .atStartOfDay(ZoneOffset.UTC).toInstant());
    }

    /**
     * Total sent this month to each favourite contact of the signed-in user.
     *
     * Amounts are in cents. Favourites that received nothing are listed
     * with a total of 0; a user without favourites gets an empty list.
     *
     * @param bearerToken HTTP request 'Authorization' header
     * @param accountId   the account of the signed-in user
     * @return list of label, accountNum, routingNum, totalSent
     */
    @GetMapping("/transactions/{accountId}/favourite-totals")
    public ResponseEntity<?> getFavouriteTotals(
            @RequestHeader("Authorization") String bearerToken,
            @PathVariable final String accountId) {
        if (!accountId.matches("^[0-9]+$")) {
            return new ResponseEntity<>("invalid account id",
                HttpStatus.BAD_REQUEST);
        }
        if (bearerToken != null && bearerToken.startsWith("Bearer ")) {
            bearerToken = bearerToken.split("Bearer ")[1];
        }
        try {
            DecodedJWT jwt = verifier.verify(bearerToken);
            if (!accountId.equals(jwt.getClaim("acct").asString())) {
                return new ResponseEntity<>("not authorized",
                    HttpStatus.UNAUTHORIZED);
            }
            String username = jwt.getClaim("user").asString();
            List<Map<String, Object>> favourites =
                contacts.getFavourites(username, bearerToken);
            List<Map<String, Object>> result = new ArrayList<>();
            if (!favourites.isEmpty()) {
                Date from = monthStart();
                Date to = nextMonthStart();
                for (Map<String, Object> fav : favourites) {
                    String acct = String.valueOf(fav.get("account_num"));
                    String route = String.valueOf(fav.get("routing_num"));
                    long total = 0;
                    for (Transaction t : dbRepo.findSentBetween(
                            accountId, route, acct, from, to)) {
                        total += t.getAmount();
                    }
                    Map<String, Object> entry = new LinkedHashMap<>();
                    entry.put("label", fav.get("label"));
                    entry.put("accountNum", acct);
                    entry.put("routingNum", route);
                    entry.put("totalSent", total);
                    result.add(entry);
                }
            }
            return new ResponseEntity<>(result, HttpStatus.OK);
        } catch (JWTVerificationException e) {
            return new ResponseEntity<>("not authorized",
                HttpStatus.UNAUTHORIZED);
        } catch (RestClientException e) {
            LOGGER.error("Could not read contacts: " + e.getMessage());
            return new ResponseEntity<>("contacts unavailable",
                HttpStatus.BAD_GATEWAY);
        }
    }
}
