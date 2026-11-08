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
Tests for the frontend's transaction history CSV export
"""

import csv
import io
import os
import unittest
from unittest.mock import MagicMock, patch, mock_open

from requests.exceptions import RequestException

import frontend

ACCOUNT = '1111111111'
ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'HISTORY_API_ADDR': 'history',
    'CONTACTS_API_ADDR': 'contacts',
}
TOKEN_DATA = {'user': 'testuser', 'acct': ACCOUNT, 'name': 'Test'}

TRANSACTIONS = [
    {'fromAccountNum': '2222222222', 'toAccountNum': ACCOUNT, 'amount': 12345,
     'timestamp': '2026-03-05T10:00:00.000+0000'},
    {'fromAccountNum': ACCOUNT, 'toAccountNum': '3333333333', 'amount': 500,
     'timestamp': '2026-03-04T09:30:00.000+0000'},
    {'fromAccountNum': ACCOUNT, 'toAccountNum': '4444444444', 'amount': 100,
     'timestamp': '2026-03-03T09:30:00.000+0000'},
]
CONTACTS = [
    {'account_num': '3333333333', 'label': 'Alice'},
    {'account_num': '4444444444', 'label': '=HYPERLINK("evil")'},
]


def _response(payload):
    resp = MagicMock()
    resp.json.return_value = payload
    resp.__bool__ = lambda self: True
    return resp


def _fake_get(history, contacts):
    def fake_get(url, **_kwargs):
        if '/transactions/' in url:
            return history() if _is_failure(history) else history
        return contacts() if _is_failure(contacts) else contacts
    return fake_get


def _is_failure(value):
    return value is _raise


def _raise():
    raise RequestException('down')


class TestTransactionsCsv(unittest.TestCase):
    """Tests the /transactions.csv route"""

    def setUp(self):
        with patch('frontend.open', mock_open(read_data='foo')), \
                patch('os.environ', dict(ENV)), \
                patch('frontend.requests.get', side_effect=RequestException):
            self.client = frontend.create_app().test_client()
        self.client.set_cookie('token', 'abc')

    def _get(self, history, contacts, valid=True):
        with patch('frontend.jwt.decode', return_value=TOKEN_DATA,
                   side_effect=None if valid else frontend.jwt.exceptions.InvalidTokenError), \
                patch('api_call.get', side_effect=_fake_get(history, contacts)):
            return self.client.get('/transactions.csv')

    def test_downloads_csv_with_expected_rows(self):
        """returns an attachment with date, description, amount and type"""
        resp = self._get(_response(TRANSACTIONS), _response(CONTACTS))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.headers['Content-Type'].startswith('text/csv'))
        self.assertIn('attachment', resp.headers['Content-Disposition'])
        rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
        self.assertEqual(rows[0], ['Date', 'Description', 'Amount', 'Type'])
        self.assertEqual(rows[1], ['2026-03-05', '2222222222', '123.45', 'Credit'])
        self.assertEqual(rows[2], ['2026-03-04', 'Alice', '-5.00', 'Debit'])

    def test_formula_characters_are_neutralized(self):
        """a contact label starting with '=' cannot become a spreadsheet formula"""
        resp = self._get(_response(TRANSACTIONS), _response(CONTACTS))
        rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
        self.assertEqual(rows[3][1], '\'=HYPERLINK("evil")')

    def test_contacts_failure_falls_back_to_account_numbers(self):
        """the export still works when contacts can't be loaded"""
        resp = self._get(_response(TRANSACTIONS), _raise)
        rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
        self.assertEqual(rows[2][1], '3333333333')

    def test_empty_history_has_only_header(self):
        """no transactions gives a header-only file"""
        resp = self._get(_response([]), _response([]))
        self.assertEqual(resp.get_data(as_text=True), 'Date,Description,Amount,Type\r\n')

    def test_history_failure_returns_error(self):
        """a failing history service gives a 502, not a bogus file"""
        resp = self._get(_raise, _response([]))
        self.assertEqual(resp.status_code, 502)

    def test_unauthenticated_redirects_to_login(self):
        """an invalid token is redirected to the login page"""
        resp = self._get(_response(TRANSACTIONS), _response(CONTACTS), valid=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers['Location'])


if __name__ == '__main__':
    unittest.main()
