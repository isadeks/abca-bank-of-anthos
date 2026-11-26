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

"""Tests for the Download CSV link and the /transactions.csv route."""

import csv
import io
import os
import unittest
from unittest.mock import MagicMock, patch, mock_open

import frontend

ACCT = '1234567890'
ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'LOCAL_ROUTING_NUM': '883745000',
}
TOKEN_DATA = {'user': 'testuser', 'acct': ACCT, 'name': 'Test'}
HISTORY = [
    {'fromAccountNum': '1111111111', 'toAccountNum': ACCT, 'amount': 12345,
     'timestamp': '2026-03-05T10:00:00.000+0000'},
    {'fromAccountNum': ACCT, 'toAccountNum': '2222222222', 'amount': 500,
     'timestamp': '2026-03-06T10:00:00.000+0000'},
    {'fromAccountNum': ACCT, 'toAccountNum': '3333333333', 'amount': 100,
     'timestamp': '2026-03-07T10:00:00.000+0000'},
]
CONTACTS = [
    {'account_num': '1111111111', 'label': 'Smith, "Bob" & Co'},
    {'account_num': '3333333333', 'label': '=SUM(A1)'},
]


def fake_call(display_name_to_data):
    """Return a make_call replacement serving canned JSON by name"""
    def make_call(self):
        resp = MagicMock()
        resp.json.return_value = display_name_to_data[self.display_name]
        return resp
    return make_call


class TestTransactionsCsv(unittest.TestCase):
    """The CSV download contains the visible transactions, escaped"""

    def setUp(self):
        patches = [
            patch('os.environ', dict(ENV)),
            patch('frontend.open', mock_open(read_data='foo')),
            patch('frontend.jwt.decode', return_value=TOKEN_DATA),
            patch('frontend.sleep'),
        ]
        for started in patches:
            started.start()
            self.addCleanup(started.stop)
        self.client = frontend.create_app().test_client()
        self.client.set_cookie('token', 'abc')

    def get_csv(self):
        """Fetch the CSV and parse it"""
        data = {name: None for name in ()}
        data.update({frontend.TRANSACTION_LIST_NAME: [dict(t) for t in HISTORY],
                     frontend.CONTACTS_NAME: CONTACTS})
        with patch('frontend.ApiCall.make_call', fake_call(data)):
            resp = self.client.get('/transactions.csv')
        return resp, list(csv.reader(io.StringIO(resp.get_data(as_text=True))))

    def test_csv_headers_and_rows(self):
        """date, description and signed amount, as an attachment"""
        resp, rows = self.get_csv()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, 'text/csv')
        self.assertIn('attachment', resp.headers['Content-Disposition'])
        self.assertEqual(rows[0], ['Date', 'Description', 'Amount'])
        self.assertEqual(rows[1][0], '2026-03-05')
        self.assertEqual(rows[1][2], '123.45')
        self.assertEqual(rows[2], ['2026-03-06', '2222222222', '-5.00'])

    def test_commas_and_quotes_are_escaped(self):
        """a label with commas and quotes survives a CSV round trip"""
        resp, rows = self.get_csv()
        self.assertEqual(rows[1][1], 'Smith, "Bob" & Co')
        self.assertIn('"Smith, ""Bob"" & Co"', resp.get_data(as_text=True))

    def test_formula_cells_are_neutralised(self):
        """a label starting with = is not a live spreadsheet formula"""
        _, rows = self.get_csv()
        self.assertEqual(rows[3][1], "'=SUM(A1)")

    def test_requires_login(self):
        """without a valid token the user is redirected to login"""
        client = frontend.create_app().test_client()
        resp = client.get('/transactions.csv')
        self.assertEqual(resp.status_code, 302)

    def test_template_has_link(self):
        """the home template links to the download under the history"""
        path = os.path.join(os.path.dirname(__file__), '..', 'templates',
                            'index.html')
        with open(path, encoding='utf-8') as f:
            html = f.read()
        self.assertRegex(html, r'id="download-csv"[^>]*>Download CSV</a>')


if __name__ == '__main__':
    unittest.main()
