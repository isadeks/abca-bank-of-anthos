# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
The home page shows how many transactions the account had this month.
"""

import datetime

from unittest.mock import MagicMock, patch

from test_payment_deposit_handlers import HandlerTestCase, backend_response


def stamp(date):
    """A transaction timestamp in the ledger's format"""
    return date.strftime('%Y-%m-%dT%H:%M:%S.%f+0000')


class TestMonthTransactions(HandlerTestCase):
    """Calendar-month count of transactions, both directions"""

    def render(self, history):
        """Render the home page with the given transaction history"""
        def fake_ctor(**kwargs):
            call = MagicMock()
            call.display_name = kwargs['display_name']
            call.make_call.return_value = (
                backend_response_json(history)
                if kwargs['display_name'] == 'transaction_list' else None)
            return call
        with patch('frontend.ApiCall', side_effect=fake_ctor):
            return self.client.get('/home').get_data(as_text=True)

    def test_counts_only_this_month(self):
        """two this month (in and out) and one last month give 2"""
        now = datetime.datetime.now(datetime.timezone.utc)
        last = now.replace(day=1) - datetime.timedelta(days=1)
        history = [
            {'fromAccountNum': '1234567890', 'toAccountNum': '1',
             'amount': 5, 'timestamp': stamp(now)},
            {'fromAccountNum': '2', 'toAccountNum': '1234567890',
             'amount': 5, 'timestamp': stamp(now)},
            {'fromAccountNum': '2', 'toAccountNum': '1234567890',
             'amount': 5, 'timestamp': stamp(last)},
        ]
        html = self.render(history)
        self.assertIn('id="month-transaction-count"', html)
        self.assertIn('2 transactions this month', html)

    def test_singular(self):
        """one transaction reads '1 transaction this month'"""
        now = datetime.datetime.now(datetime.timezone.utc)
        html = self.render([{'fromAccountNum': '1234567890',
                             'toAccountNum': '1', 'amount': 5,
                             'timestamp': stamp(now)}])
        self.assertIn('1 transaction this month', html)

    def test_zero(self):
        """an empty history reads '0 transactions this month'"""
        self.assertIn('0 transactions this month', self.render([]))

    def test_hidden_without_history(self):
        """no line when the history could not be loaded"""
        self.assertNotIn('month-transaction-count', self.render(None))


def backend_response_json(data):
    """A fake backend response carrying JSON"""
    resp = backend_response(200)
    resp.json.return_value = data
    return resp
