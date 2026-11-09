// Copyright 2020 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package anthos.samples.bankofanthos.transactionhistory;

import java.util.LinkedList;
import java.util.List;

import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.CrudRepository;
import org.springframework.stereotype.Repository;

/**
 * Repository class for performing queries on the Transaction database
 */
@Repository
public interface TransactionRepository
        extends CrudRepository<Transaction, Long> {

    /**
     * Returns the id of the latest transaction, or NULL if none exist.
     */
    @Query("SELECT MAX(transactionId) FROM Transaction")
    Long latestTransactionId();

    /**
     * Returns the newest transactions of an account, newest first.
     *
     * Written as the union of two index-ordered, limited scans instead of
     * one query with an OR condition. With the OR, Postgres has to fetch and
     * sort every transaction of the account before it can apply the page
     * size, which is slow for accounts with many transactions. Each branch
     * below walks the (ACCT, ROUTE, TIMESTAMP) index of the ledger from the
     * newest entry and stops after the page, so the cost depends on the page
     * size and not on the size of the account. The parameters are cast to
     * the CHAR type of the columns so that the index can be used.
     * UNION (not UNION ALL) keeps a transfer to oneself from showing twice.
     */
    @Query(value = "SELECT * FROM ("
        + " (SELECT * FROM TRANSACTIONS "
        + "   WHERE FROM_ACCT = CAST(?1 AS CHAR(10)) "
        + "     AND FROM_ROUTE = CAST(?2 AS CHAR(9)) "
        + "   ORDER BY TIMESTAMP DESC "
        + "   LIMIT ?#{[2].offset + [2].pageSize}) "
        + " UNION "
        + " (SELECT * FROM TRANSACTIONS "
        + "   WHERE TO_ACCT = CAST(?1 AS CHAR(10)) "
        + "     AND TO_ROUTE = CAST(?2 AS CHAR(9)) "
        + "   ORDER BY TIMESTAMP DESC "
        + "   LIMIT ?#{[2].offset + [2].pageSize}) "
        + ") history ORDER BY TIMESTAMP DESC",
        nativeQuery = true)
    LinkedList<Transaction> findForAccount(String accountNum,
                                           String routingNum,
                                           Pageable pager);

    @Query("SELECT t FROM Transaction t "
        + " WHERE t.transactionId > ?1 ORDER BY t.transactionId ASC")
    List<Transaction> findLatest(long latestTransaction);
}
