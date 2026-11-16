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

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.Transient;
import java.util.Date;
import org.hibernate.annotations.CreationTimestamp;

/**
 * Defines a banking transaction.
 *
 * Timestamped at object creation time.
 */
@Entity
@Table(name = "TRANSACTIONS")
public final class Transaction {
    @Id
    @Column(name = "TRANSACTION_ID", nullable = false, updatable = false)
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private long transactionId;
    @Column(name = "FROM_ACCT", nullable = false, updatable = false)
    @JsonProperty("fromAccountNum")
    private String fromAccountNum;
    @Column(name = "FROM_ROUTE", nullable = false, updatable = false)
    @JsonProperty("fromRoutingNum")
    private String fromRoutingNum;
    @Column(name = "TO_ACCT", nullable = false, updatable = false)
    @JsonProperty("toAccountNum")
    private String toAccountNum;
    @Column(name = "TO_ROUTE", nullable = false, updatable = false)
    @JsonProperty("toRoutingNum")
    private String toRoutingNum;
    @Column(name = "AMOUNT", nullable = false, updatable = false)
    @JsonProperty("amount")
    private Integer amount;
    @Column(name = "TIMESTAMP", nullable = false, updatable = false)
    @CreationTimestamp
    @JsonProperty("timestamp")
    private Date timestamp;

    @Column(name = "CATEGORY", nullable = false, updatable = false)
    // Not mapped to the CATEGORY column: the column may not exist yet in
    // older ledger databases. Loaded separately, see
    // TransactionRepository.loadCategories.
    @Transient
    @JsonProperty("category")
    private String category = DEFAULT_CATEGORY;

    public static final String DEFAULT_CATEGORY = "Other";
    public static final java.util.List<String> CATEGORIES = java.util.List.of(
        "Groceries", "Rent", "Transport", "Eating out", DEFAULT_CATEGORY);

    private static final double CENTS_PER_DOLLAR = 100.0;

    public long getTransactionId() {
        return transactionId;
    }

    public String getFromAccountNum() {
        return fromAccountNum;
    }

    public String getFromRoutingNum() {
        return fromRoutingNum;
    }

    public String getToAccountNum() {
        return toAccountNum;
    }

    public String getToRoutingNum() {
        return toRoutingNum;
    }

    public Integer getAmount() {
        return amount;
    }

    /**
     * Category of the transaction; a missing or unknown one is "Other".
     */
    @JsonProperty("category")
    public String getCategory() {
        return normalizeCategory(category);
    }

    void setCategory(String value) {
        this.category = normalizeCategory(value);
    }

    /**
     * Maps a category to a known one (case-insensitive), else "Other".
     */
    public static String normalizeCategory(String value) {
        if (value != null) {
            String trimmed = value.trim();
            for (String known : CATEGORIES) {
                if (known.equalsIgnoreCase(trimmed)) {
                    return known;
                }
            }
        }
        return DEFAULT_CATEGORY;
    }
    /**
     * String representation.
     *
     * Formatting = "{accountNum}:{type}:{amount}"
     */
    public String toString() {
        return String.format("%s->$%.2f->%s",
                fromAccountNum, amount / CENTS_PER_DOLLAR, toAccountNum);
    }
}
