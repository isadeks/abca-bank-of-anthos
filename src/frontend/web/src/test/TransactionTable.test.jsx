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

import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import TransactionTable from '../components/TransactionTable.jsx';

const history = [
  { timestamp: '2021-03-07T12:00:00.000+0000', fromAccountNum: '1111111111', toAccountNum: '2222222222', amount: 12345, accountLabel: 'Alice' },
  { timestamp: '2021-03-06T12:00:00.000+0000', fromAccountNum: '3333333333', toAccountNum: '1111111111', amount: 500, accountLabel: null },
];

describe('TransactionTable', () => {
  it('shows debits and credits of the account', () => {
    render(<TransactionTable accountId="1111111111" history={history} />);
    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent('Mar 07');
    expect(rows[0]).toHaveTextContent('Debit');
    expect(rows[0]).toHaveTextContent('2222222222');
    expect(rows[0]).toHaveTextContent('Alice');
    expect(rows[0]).toHaveTextContent('-$123.45');
    expect(rows[1]).toHaveTextContent('Credit');
    expect(rows[1]).toHaveTextContent('3333333333');
    expect(rows[1]).toHaveTextContent('None');
    expect(rows[1]).toHaveTextContent('+$5.00');
  });

  it('says so when there are no transactions', () => {
    render(<TransactionTable accountId="1111111111" history={[]} />);
    expect(screen.getByText('No Transactions Found')).toBeInTheDocument();
  });

  it('says so when the history could not be loaded', () => {
    render(<TransactionTable accountId="1111111111" history={null} />);
    expect(screen.getByText('Error: Could Not Load Transactions')).toBeInTheDocument();
  });
});
