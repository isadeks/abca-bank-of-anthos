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

import static anthos.samples.bankofanthos.ledgerwriter.ExceptionMessages.EXCEPTION_MESSAGE_INVALID_POCKET_TRANSFER;
import static anthos.samples.bankofanthos.ledgerwriter.ExceptionMessages.EXCEPTION_MESSAGE_NOT_AUTHENTICATED;
import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * Rules for transfers involving the Savings pocket: a second ledger account
 * with the owner's account number under the savings routing number.
 */
class SavingsPocketValidatorTest {

    private static final String LOCAL = "123456789";
    private static final String SAVINGS = "123456999";
    private static final String EXTERNAL = "987654321";
    private static final String ME = "1234567890";
    private static final String OTHER = "0987654321";

    private final TransactionValidator validator = new TransactionValidator();

    private static Transaction tx(String fromAcct, String fromRoute,
            String toAcct, String toRoute, int amount) throws Exception {
        String json = String.format(
            "{\"fromAccountNum\":\"%s\",\"fromRoutingNum\":\"%s\","
                + "\"toAccountNum\":\"%s\",\"toRoutingNum\":\"%s\","
                + "\"amount\":%d,\"uuid\":\"%s\"}",
            fromAcct, fromRoute, toAcct, toRoute, amount, UUID.randomUUID());
        return new ObjectMapper().readValue(json, Transaction.class);
    }

    private void validate(Transaction t) {
        validator.validateTransaction(LOCAL, SAVINGS, ME, t);
    }

    private void assertRejected(Transaction t, String message) {
        IllegalArgumentException e = assertThrows(
            IllegalArgumentException.class, () -> validate(t));
        assertEquals(message, e.getMessage());
    }

    @Test
    @DisplayName("Main account to own pocket is allowed")
    void mainToOwnPocket() throws Exception {
        assertDoesNotThrow(() -> validate(tx(ME, LOCAL, ME, SAVINGS, 500)));
    }

    @Test
    @DisplayName("Own pocket to main account is allowed")
    void pocketToOwnMain() throws Exception {
        assertDoesNotThrow(() -> validate(tx(ME, SAVINGS, ME, LOCAL, 500)));
    }

    @Test
    @DisplayName("Pocket to another customer's account is rejected")
    void pocketToOtherCustomer() throws Exception {
        assertRejected(tx(ME, SAVINGS, OTHER, LOCAL, 500),
            EXCEPTION_MESSAGE_INVALID_POCKET_TRANSFER);
    }

    @Test
    @DisplayName("Pocket to an external account is rejected")
    void pocketToExternal() throws Exception {
        assertRejected(tx(ME, SAVINGS, ME, EXTERNAL, 500),
            EXCEPTION_MESSAGE_INVALID_POCKET_TRANSFER);
    }

    @Test
    @DisplayName("Deposit from an external account into a pocket is rejected")
    void externalToPocket() throws Exception {
        assertRejected(tx(OTHER, EXTERNAL, ME, SAVINGS, 500),
            EXCEPTION_MESSAGE_INVALID_POCKET_TRANSFER);
    }

    @Test
    @DisplayName("Another customer's main account to my pocket is rejected")
    void otherMainToMyPocket() throws Exception {
        assertRejected(tx(OTHER, LOCAL, ME, SAVINGS, 500),
            EXCEPTION_MESSAGE_NOT_AUTHENTICATED);
    }

    @Test
    @DisplayName("My main account to another customer's pocket is rejected")
    void myMainToOtherPocket() throws Exception {
        assertRejected(tx(ME, LOCAL, OTHER, SAVINGS, 500),
            EXCEPTION_MESSAGE_INVALID_POCKET_TRANSFER);
    }

    @Test
    @DisplayName("Spending from another customer's pocket is rejected")
    void spendingFromOtherPocket() throws Exception {
        assertRejected(tx(OTHER, SAVINGS, OTHER, LOCAL, 500),
            EXCEPTION_MESSAGE_NOT_AUTHENTICATED);
    }

    @Test
    @DisplayName("Pocket to pocket is rejected")
    void pocketToPocket() throws Exception {
        assertThrows(IllegalArgumentException.class,
            () -> validate(tx(ME, SAVINGS, ME, SAVINGS, 500)));
    }

    @Test
    @DisplayName("Without a savings routing number, pockets are not special")
    void pocketsDisabled() throws Exception {
        assertDoesNotThrow(() -> validator.validateTransaction(
            LOCAL, null, ME, tx(ME, LOCAL, OTHER, SAVINGS, 500)));
    }

    @Test
    @DisplayName("Ordinary transfers are unaffected when pockets are enabled")
    void ordinaryTransfers() throws Exception {
        assertDoesNotThrow(() -> validate(tx(ME, LOCAL, OTHER, LOCAL, 500)));
        assertDoesNotThrow(() -> validate(tx(OTHER, EXTERNAL, ME, LOCAL, 500)));
    }
}
