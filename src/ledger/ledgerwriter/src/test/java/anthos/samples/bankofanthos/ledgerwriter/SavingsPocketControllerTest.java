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

package anthos.samples.bankofanthos.ledgerwriter;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.spy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.interfaces.Claim;
import com.auth0.jwt.interfaces.DecodedJWT;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

/**
 * The controller accepts only own main <-> own pocket transfers for the
 * savings routing number and checks the pocket balance when spending from it.
 */
class SavingsPocketControllerTest {

    private static final String LOCAL = "123456789";
    private static final String SAVINGS = "123456999";
    private static final String EXTERNAL = "987654321";
    private static final String ME = "1234567890";
    private static final String OTHER = "0987654321";

    private TransactionRepository repository;
    private LedgerWriterController controller;

    private static Transaction tx(String fromAcct, String fromRoute,
            String toAcct, String toRoute, int amount) throws Exception {
        String json = String.format(
            "{\"fromAccountNum\":\"%s\",\"fromRoutingNum\":\"%s\","
                + "\"toAccountNum\":\"%s\",\"toRoutingNum\":\"%s\","
                + "\"amount\":%d,\"uuid\":\"%s\"}",
            fromAcct, fromRoute, toAcct, toRoute, amount, UUID.randomUUID());
        return new ObjectMapper().readValue(json, Transaction.class);
    }

    @BeforeEach
    void setUp() {
        JWTVerifier verifier = mock(JWTVerifier.class);
        DecodedJWT jwt = mock(DecodedJWT.class);
        Claim claim = mock(Claim.class);
        when(verifier.verify("abc")).thenReturn(jwt);
        when(jwt.getClaim(LedgerWriterController.JWT_ACCOUNT_KEY))
            .thenReturn(claim);
        when(claim.asString()).thenReturn(ME);
        repository = mock(TransactionRepository.class);
        controller = spy(new LedgerWriterController(verifier,
            new SimpleMeterRegistry(), repository, new TransactionValidator(),
            LOCAL, SAVINGS, "balancereader:8080", "v0"));
    }

    @Test
    @DisplayName("Moving the pocket back to the main account is accepted when "
        + "the pocket covers it")
    void moveBackAccepted() throws Exception {
        doReturn(1000).when(controller)
            .getAvailableBalance("abc", ME, SAVINGS);

        ResponseEntity<?> r = controller.addTransaction(
            "Bearer abc", tx(ME, SAVINGS, ME, LOCAL, 1000));

        assertEquals(HttpStatus.CREATED, r.getStatusCode());
        verify(repository).save(any(Transaction.class));
    }

    @Test
    @DisplayName("Spending more than the pocket holds is rejected")
    void overdrawingPocketRejected() throws Exception {
        doReturn(999).when(controller)
            .getAvailableBalance("abc", ME, SAVINGS);

        ResponseEntity<?> r = controller.addTransaction(
            "Bearer abc", tx(ME, SAVINGS, ME, LOCAL, 1000));

        assertEquals(HttpStatus.BAD_REQUEST, r.getStatusCode());
        verify(repository, never()).save(any(Transaction.class));
    }

    @Test
    @DisplayName("Moving money into the pocket checks the main balance")
    void toPocketChecksMainBalance() throws Exception {
        doReturn(500).when(controller).getAvailableBalance("abc", ME);

        ResponseEntity<?> r = controller.addTransaction(
            "Bearer abc", tx(ME, LOCAL, ME, SAVINGS, 1000));

        assertEquals(HttpStatus.BAD_REQUEST, r.getStatusCode());
        verify(repository, never()).save(any(Transaction.class));
    }

    @Test
    @DisplayName("Anything else involving the pocket is rejected unsaved")
    void otherPocketTransfersRejected() throws Exception {
        Transaction[] bad = {
            tx(ME, SAVINGS, OTHER, LOCAL, 100),
            tx(ME, SAVINGS, ME, EXTERNAL, 100),
            tx(EXTERNAL, EXTERNAL, ME, SAVINGS, 100),
            tx(OTHER, SAVINGS, OTHER, LOCAL, 100),
            tx(ME, LOCAL, OTHER, SAVINGS, 100),
        };
        for (Transaction t : bad) {
            ResponseEntity<?> r = controller.addTransaction("Bearer abc", t);
            assertEquals(HttpStatus.BAD_REQUEST, r.getStatusCode());
        }
        verify(repository, never()).save(any(Transaction.class));
        verify(controller, never()).getAvailableBalance(
            anyString(), anyString(), anyString());
    }
}
