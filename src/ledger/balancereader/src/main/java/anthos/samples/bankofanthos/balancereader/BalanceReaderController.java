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

import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.exceptions.JWTVerificationException;
import com.auth0.jwt.interfaces.DecodedJWT;
import com.google.common.cache.LoadingCache;
import com.google.common.util.concurrent.UncheckedExecutionException;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.binder.cache.GuavaCacheMetrics;
import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import java.util.concurrent.ExecutionException;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/**
 * REST service to retrieve the current balance for the authenticated user.
 */
@RestController
public final class BalanceReaderController {

    private static final Logger LOGGER =
        LogManager.getLogger(BalanceReaderController.class);

    /** Span attribute: routing number of the account. */
    static final String ROUTING_NUM_TAG = "balance.routing_num";
    /** Span attribute: whether the balance came from the cache. */
    static final String CACHE_HIT_TAG = "balance.cache_hit";

    @Autowired
    private TransactionRepository dbRepo;

    private String localRoutingNum;
    private String version;

    private JWTVerifier verifier;
    private LoadingCache<String, Long> cache;
    private LedgerReader ledgerReader;
    private Tracer tracer;

    /**
     * Constructor without tracing: no span attributes are recorded.
     *
     * @param reader          ledger reader
     * @param verifier        JWT verifier
     * @param meterRegistry   metrics registry
     * @param cache           balance cache
     * @param localRoutingNum routing number of this bank
     * @param version         service version
     */
    public BalanceReaderController(LedgerReader reader,
        JWTVerifier verifier,
        MeterRegistry meterRegistry,
        LoadingCache<String, Long> cache,
        final String localRoutingNum,
        final String version) {
        this(reader, verifier, meterRegistry, cache, localRoutingNum,
            version, null);
    }

    /**
     * Constructor.
     *
     * Initializes JWT verifier and a connection to the bank ledger.
     * The tracer is used to tag balance reads with the routing number and
     * whether the balance came from the cache.
     */
    @Autowired
    public BalanceReaderController(LedgerReader reader,
        JWTVerifier verifier,
        MeterRegistry meterRegistry,
        LoadingCache<String, Long> cache,
        @Value("${LOCAL_ROUTING_NUM}") final String localRoutingNum,
        @Value("${VERSION}") final String version,
        ObjectProvider<Tracer> tracerProvider) {
        // The tracer is optional: contexts without tracing still work.
        this.tracer = tracerProvider == null
            ? null : tracerProvider.getIfAvailable();
        this.localRoutingNum = localRoutingNum;
        // Initialize JWT verifier.
        this.verifier = verifier;
        LOGGER.debug("Initialized JWT verifier");
        // Initialize cache
        this.cache = cache;
        GuavaCacheMetrics.monitor(meterRegistry, this.cache, "Guava");
        LOGGER.debug("Initialized cache");
        this.version = version;
        // Initialize transaction processor.
        this.ledgerReader = reader;
        LOGGER.debug("Initialized transaction processor");
        this.ledgerReader.startWithCallback(transaction -> {
            final String fromId = transaction.getFromAccountNum();
            final String fromRouting = transaction.getFromRoutingNum();
            final String toId = transaction.getToAccountNum();
            final String toRouting = transaction.getToRoutingNum();
            final Integer amount = transaction.getAmount();

            if (fromRouting.equals(localRoutingNum)
                && this.cache.asMap().containsKey(fromId)) {
                Long prevBalance = cache.asMap().get(fromId);
                this.cache.put(fromId, prevBalance - amount);
            }
            if (toRouting.equals(localRoutingNum)
                && this.cache.asMap().containsKey(toId)) {
                Long prevBalance = cache.asMap().get(toId);
                this.cache.put(toId, prevBalance + amount);
            }
        });
    }

    /**
     * Version endpoint.
     *
     * @return  service version string
     */
    @GetMapping("/version")
    public ResponseEntity version() {
        return new ResponseEntity<>(version, HttpStatus.OK);
    }

    /**
     * Readiness probe endpoint.
     *
     * @return HTTP Status 200 if server is ready to receive requests.
     */
    @GetMapping("/ready")
    @ResponseStatus(HttpStatus.OK)
    public String readiness() {
        return "ok";
    }

    /**
     * Liveness probe endpoint.
     *
     * @return HTTP Status 200 if server is healthy and serving requests.
     */
    @GetMapping("/healthy")
    public ResponseEntity liveness() {
        if (!ledgerReader.isAlive()) {
            // Background thread died.
            LOGGER.error("Ledger reader not healthy");
            return new ResponseEntity<>("Ledger reader not healthy",
                HttpStatus.INTERNAL_SERVER_ERROR);
        }
        return new ResponseEntity<>("ok", HttpStatus.OK);
    }

    /**
     * Return the balance for the specified account.
     *
     * The currently authenticated user must be allowed to access the account.
     *
     * @param bearerToken  HTTP request 'Authorization' header
     * @param accountId    the account to get the balance for
     * @return             the balance of the account
     */
    @GetMapping("/balances/{accountId}")
    public ResponseEntity<?> getBalance(
        @RequestHeader("Authorization") String bearerToken,
        @PathVariable String accountId) {

        if (bearerToken != null && bearerToken.startsWith("Bearer ")) {
            bearerToken = bearerToken.split("Bearer ")[1];
        }
        try {
            DecodedJWT jwt = verifier.verify(bearerToken);
            // Check that the authenticated user can access this account.
            if (!accountId.equals(jwt.getClaim("acct").asString())) {
                LOGGER.error("Failed to retrieve account balance: "
                    + "not authorized");
                return new ResponseEntity<>("not authorized",
                    HttpStatus.UNAUTHORIZED);
            }
            // containsKey does not touch the cache statistics.
            boolean cacheHit = cache.asMap() != null
                && cache.asMap().containsKey(accountId);
            tagSpan(cacheHit);
            // Load from cache
            Long balance = cache.get(accountId);
            return new ResponseEntity<Long>(balance, HttpStatus.OK);
        } catch (JWTVerificationException e) {
            LOGGER.error("Failed to retrieve account balance: not authorized");
            return new ResponseEntity<>("not authorized",
                HttpStatus.UNAUTHORIZED);
        } catch (ExecutionException | UncheckedExecutionException e) {
            LOGGER.error("Cache error");
            return new ResponseEntity<>("cache error",
                HttpStatus.INTERNAL_SERVER_ERROR);
        }
    }

    /**
     * Tags the current span with the routing number and cache-hit flag.
     * The account number is deliberately not recorded.
     *
     * @param cacheHit  whether the balance is served from the cache
     */
    private void tagSpan(final boolean cacheHit) {
        if (tracer == null) {
            return;
        }
        Span span = tracer.currentSpan();
        if (span == null) {
            return;
        }
        span.tag(ROUTING_NUM_TAG, String.valueOf(localRoutingNum));
        span.tag(CACHE_HIT_TAG, cacheHit);
    }
}
