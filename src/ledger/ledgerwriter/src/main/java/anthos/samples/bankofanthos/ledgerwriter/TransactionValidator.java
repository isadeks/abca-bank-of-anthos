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

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.springframework.stereotype.Component;

import java.util.regex.Pattern;

import static anthos.samples.bankofanthos.ledgerwriter.ExceptionMessages.
        EXCEPTION_MESSAGE_INVALID_NUMBER;
import static anthos.samples.bankofanthos.ledgerwriter.ExceptionMessages.
        EXCEPTION_MESSAGE_NOT_AUTHENTICATED;
import static anthos.samples.bankofanthos.ledgerwriter.ExceptionMessages.
        EXCEPTION_MESSAGE_SEND_TO_SELF;
import static anthos.samples.bankofanthos.ledgerwriter.ExceptionMessages.
        EXCEPTION_MESSAGE_INVALID_AMOUNT;
import static anthos.samples.bankofanthos.ledgerwriter.ExceptionMessages.
        EXCEPTION_MESSAGE_INVALID_POCKET_TRANSFER;


/**
 * Validator to authenticate transaction.
 *
 * Functions to validate transaction details before adding to the ledger.
 */
@Component
public class TransactionValidator {

    // account ids should be 10 digits between 0 and 9
    private static final Pattern ACCT_REGEX = Pattern.compile("^[0-9]{10}$");
    // route numbers should be 9 digits between 0 and 9
    private static final Pattern ROUTE_REGEX = Pattern.compile("^[0-9]{9}$");

    private static final Logger LOGGER =
        LogManager.getLogger(TransactionValidator.class);

    /**
     *   - Ensure sender is the same user authenticated by auth token
     *   - Ensure account and routing numbers are in the correct format
     *   - Ensure sender and receiver are different accounts
     *   - Ensure amount is positive
     *
     * @param authedAccount  the currently authenticated user account
     * @param transaction    the transaction object
     * @param bearerToken    the token used to authenticate request
     *
     * @throws IllegalArgumentException  on validation error
     */
    public void validateTransaction(String localRoutingNum, String authedAcct,
                                     Transaction transaction)
            throws IllegalArgumentException {
        validateTransaction(localRoutingNum, null, authedAcct, transaction);
    }

    /**
     * Same checks as above, plus the rules for the Savings pocket: a second
     * ledger account that uses the owner's account number under the reserved
     * savings routing number.
     *
     *   - Only the owner can spend from their pocket
     *   - A transaction involving the savings routing number must move money
     *     between the owner's main account and the owner's pocket, and
     *     nothing else
     *
     * @param localRoutingNum    the routing number of this bank
     * @param savingsRoutingNum  the reserved savings pocket routing number,
     *                           or null/empty if pockets are not configured
     * @param authedAcct         the currently authenticated user account
     * @param transaction        the transaction object
     *
     * @throws IllegalArgumentException  on validation error
     */
    public void validateTransaction(String localRoutingNum,
                                     String savingsRoutingNum,
                                     String authedAcct,
                                     Transaction transaction)
            throws IllegalArgumentException {
        final boolean pocketsEnabled =
                savingsRoutingNum != null && !savingsRoutingNum.isEmpty();
        LOGGER.debug("Validating transaction");
        final String fromAcct = transaction.getFromAccountNum();
        final String fromRoute = transaction.getFromRoutingNum();
        final String toAcct = transaction.getToAccountNum();
        final String toRoute = transaction.getToRoutingNum();
        final Integer amount = transaction.getAmount();

        // Validate account and routing numbers.
        if (!ACCT_REGEX.matcher(fromAcct).matches()
                || !ACCT_REGEX.matcher(toAcct).matches()
                || !ROUTE_REGEX.matcher(
                        fromRoute).matches()
                || !ROUTE_REGEX.matcher(
                        toRoute).matches()) {
            LOGGER.error("Invalid transaction: Invalid account details");
            throw new IllegalArgumentException(
                    EXCEPTION_MESSAGE_INVALID_NUMBER);
        }
        // If this is an internal transaction (main account or savings pocket),
        // ensure it originated from the authenticated user.
        if ((fromRoute.equals(localRoutingNum)
                || (pocketsEnabled && fromRoute.equals(savingsRoutingNum)))
                && !fromAcct.equals(authedAcct)) {
            LOGGER.error("Invalid transaction: Sender not authorized");
            throw new IllegalArgumentException(
                    EXCEPTION_MESSAGE_NOT_AUTHENTICATED);
        }
        // Anything involving the savings routing number must be a transfer
        // between the owner's main account and the owner's own pocket.
        if (pocketsEnabled && (fromRoute.equals(savingsRoutingNum)
                || toRoute.equals(savingsRoutingNum))) {
            final boolean mainToPocket = fromRoute.equals(localRoutingNum)
                    && toRoute.equals(savingsRoutingNum);
            final boolean pocketToMain = fromRoute.equals(savingsRoutingNum)
                    && toRoute.equals(localRoutingNum);
            if (!(mainToPocket || pocketToMain)
                    || !fromAcct.equals(authedAcct)
                    || !toAcct.equals(authedAcct)) {
                LOGGER.error("Invalid transaction: Invalid savings pocket "
                        + "transfer");
                throw new IllegalArgumentException(
                        EXCEPTION_MESSAGE_INVALID_POCKET_TRANSFER);
            }
        }
        // Ensure sender isn't receiver.
        if (fromAcct.equals(toAcct) && fromRoute.equals(toRoute)) {
            LOGGER.error("Invalid transaction: Sender is also receiver");
            throw new IllegalArgumentException(EXCEPTION_MESSAGE_SEND_TO_SELF);
        }
        // Ensure amount is valid value.
        if (amount <= 0) {
            LOGGER.error("Invalid transaction: Transaction amount invalid");
            throw new IllegalArgumentException(
                    EXCEPTION_MESSAGE_INVALID_AMOUNT);
        }
    }
}
