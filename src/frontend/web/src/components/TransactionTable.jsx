// Copyright 2026 Google LLC
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

/**
 * Calls to the JSON API of the Flask service. Anything but a 2xx answer
 * rejects with an ApiError that carries the HTTP status and the service's
 * message.
 */
import { formatCurrency, formatDate } from '../format.js';

function Label({ value }) {
  return value === null || value === undefined ? (
    <span className="transaction-label-none">None</span>
  ) : (
    value
  );
}

/** The transaction history of an account; `history` is null when it could not be loaded. */
export default function TransactionTable({ accountId, history }) {
  let content;
  if (history === null || history === undefined) {
    content = <h4 className="card-table-header">Error: Could Not Load Transactions</h4>;
  } else if (history.length === 0) {
    content = <h4 className="card-table-header">No Transactions Found</h4>;
  } else {
    content = (
      <table className="table table-sm table-nowrap card-table">
        <thead className="text-uppercase">
          <tr>
            <th><a className="text-transaction-header">Date</a></th>
            <th><a className="text-transaction-header">Type</a></th>
            <th><a className="text-transaction-header">Account</a></th>
            <th><a className="text-transaction-header">Label</a></th>
            <th className="text-right"><a className="text-transaction-header">Amount</a></th>
          </tr>
        </thead>
        <tbody className="list" id="transaction-list">
          {history.map((t, index) => {
            const credit = t.toAccountNum === accountId;
            if (!credit && t.fromAccountNum !== accountId) {
              return null;
            }
            return (
              <tr key={`${t.timestamp}-${index}`}>
                <td className="text-uppercase transaction-date">
                  <p>{formatDate(t.timestamp)}</p>
                </td>
                <td className="transaction-type">
                  <span className={credit ? 'text-debit' : 'text-credit'}>●</span> {credit ? 'Credit' : 'Debit'}
                </td>
                <td className="transaction-account">{credit ? t.fromAccountNum : t.toAccountNum}</td>
                <td className="transaction-label"><Label value={t.accountLabel} /></td>
                <td className={`transaction-amount transaction-amount-${credit ? 'credit' : 'debit'}`}>
                  {credit ? '+' : '-'}{formatCurrency(t.amount)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  }
  return (
    <div className="table-responsive mb-0" id="transaction-table">
      {content}
    </div>
  );
}
