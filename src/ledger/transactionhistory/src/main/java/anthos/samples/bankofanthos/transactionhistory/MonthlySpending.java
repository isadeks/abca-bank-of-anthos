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

import java.util.List;

/**
 * The outgoing spending of one account in one calendar month.
 *
 * @param month          the calendar month, formatted as "YYYY-MM"
 * @param counterparties totals per counterparty, largest total first
 */
public record MonthlySpending(String month,
                              List<CounterpartySpending> counterparties) {
}
