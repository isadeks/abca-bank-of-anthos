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

/**
 * The total an account sent to one counterparty in a month.
 *
 * A counterparty is identified by its account number and routing number.
 * Showing a contact label or the last digits of the number is left to the
 * caller.
 *
 * @param counterpartyAccountNum the receiving account number
 * @param counterpartyRoutingNum the receiving routing number
 * @param totalCents             the total amount sent, in cents
 */
public record CounterpartySpending(String counterpartyAccountNum,
                                   String counterpartyRoutingNum,
                                   long totalCents) {
}
