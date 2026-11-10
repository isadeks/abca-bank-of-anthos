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
Tests that the home page shows a transaction search box above the history,
and the hidden "No matching transactions" message the search script reveals.
"""

import os
import unittest
from unittest.mock import MagicMock, patch, mock_open

from requests.exceptions import RequestException

import frontend

ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'LOCAL_ROUTING_NUM': '883745000',
}
ACCOUNT = '1234567890'
TOKEN_DATA = {'user': 'testuser', 'acct': ACCOUNT, 'name': 'Test'}
HISTORY = [
    {'fromAccountNum': ACCOUNT, 'toAccountNum': '1055757655',
     'amount': 1000, 'timestamp': '2024-01-02T03:04:05.000+0000'},
    {'fromAccountNum': '1033623433', 'toAccountNum': ACCOUNT,
     'amount': 2000, 'timestamp': '2024-01-03T03:04:05.000+0000'},
]
CONTACTS = [{'label': 'Alice', 'account_num': '1055757655',
             'routing_num': '883745000', 'is_external': False}]


def json_response(data):
    """A fake backend response carrying JSON"""
    resp = MagicMock()
    resp.json.return_value = data
    return resp


class TestTransactionSearch(unittest.TestCase):
    """The search box is rendered above the transaction history"""

    def render_home(self, history):
        """Render the home page with the given transaction history"""
        def make_call(call):
            return {
                'transaction_list': json_response(history) if history is not None else None,
                'contacts': json_response(CONTACTS),
                'balance': json_response(5000),
            }.get(call.display_name)

        with patch('os.environ', dict(ENV)), \
                patch('frontend.open', mock_open(read_data='foo')), \
                patch('frontend.requests.get', side_effect=RequestException), \
                patch('frontend.jwt.decode', return_value=TOKEN_DATA), \
                patch('frontend.ApiCall.make_call', autospec=True,
                      side_effect=make_call):
            client = frontend.create_app().test_client()
            client.set_cookie('token', 'abc')
            resp = client.get('/home')
        self.assertEqual(resp.status_code, 200)
        return resp.get_data(as_text=True)

    def test_search_box_above_history(self):
        """the search box comes before the transaction table"""
        body = self.render_home(HISTORY)
        self.assertIn('id="transaction-search"', body)
        self.assertLess(body.index('id="transaction-search"'),
                        body.index('id="transaction-list"'))

    def test_no_match_message_is_hidden_by_default(self):
        """the message exists but starts hidden"""
        body = self.render_home(HISTORY)
        self.assertRegex(
            body,
            r'class="[^"]*hidden[^"]*" id="no-matching-transactions">'
            r'No matching transactions<')

    def test_no_match_message_is_not_a_table_header(self):
        """the e2e login spec expects no card-table-header inside the table"""
        body = self.render_home(HISTORY)
        start = body.index('id="transaction-table"')
        end = body.index('No matching transactions<', start)
        # between the table container and the message, only the real
        # (error/empty) header class would appear; it must not here
        self.assertNotIn('card-table-header', body[start:end + 30])

    def test_rows_expose_account_and_label(self):
        """the cells the script filters on are present"""
        body = self.render_home(HISTORY)
        self.assertIn('1055757655', body)
        self.assertIn('Alice', body)
        self.assertIn('transaction-account', body)
        self.assertIn('transaction-label', body)

    def test_no_search_box_without_transactions(self):
        """nothing to search when the history is empty"""
        body = self.render_home([])
        self.assertNotIn('id="transaction-search"', body)
        self.assertIn('No Transactions Found', body)


if __name__ == '__main__':
    unittest.main()
