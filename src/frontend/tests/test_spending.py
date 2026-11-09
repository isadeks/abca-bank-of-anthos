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
Unit tests for the "Spending by counterparty" section of the home page:
contact labels, the last 4 digits fallback, the empty state and a failed call.
"""

import re
import unittest
from unittest.mock import MagicMock, patch, mock_open

from requests.exceptions import RequestException

import frontend

LOCAL_ROUTING = '883745000'
ACCOUNT_ID = '1234567890'
ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'LOCAL_ROUTING_NUM': LOCAL_ROUTING,
    'BALANCES_API_ADDR': 'balances',
    'HISTORY_API_ADDR': 'history',
    'CONTACTS_API_ADDR': 'contacts',
}
TOKEN_DATA = {'user': 'testuser', 'acct': ACCOUNT_ID, 'name': 'Test'}
CONTACTS = [{'label': 'Alice', 'account_num': '1111111111',
             'routing_num': LOCAL_ROUTING, 'is_external': False}]
SPENDING = [
    {'month': '2026-11', 'counterparties': [
        {'counterpartyAccountNum': '1111111111',
         'counterpartyRoutingNum': LOCAL_ROUTING, 'totalCents': 123456},
        {'counterpartyAccountNum': '2222223333',
         'counterpartyRoutingNum': LOCAL_ROUTING, 'totalCents': 5}]},
    {'month': '2026-10', 'counterparties': [
        {'counterpartyAccountNum': '2222223333',
         'counterpartyRoutingNum': LOCAL_ROUTING, 'totalCents': 2000}]},
]


def json_response(body, ok=True):
    """A fake backend response with a JSON body"""
    resp = MagicMock()
    resp.__bool__.return_value = ok
    resp.json.return_value = body
    return resp


def text_of(pattern, html):
    """The stripped text of the first match of the pattern, or None"""
    found = re.search(pattern, html, re.S)
    return found.group(1).strip() if found else None


class SpendingTestCase(unittest.TestCase):
    """Renders the home page with every backend call faked by URL"""

    def setUp(self):
        self.responses = {
            '/balances/': json_response(100000),
            '/transactions/': json_response([]),
            '/contacts/': json_response(CONTACTS),
            '/spending/': json_response(SPENDING),
        }
        self.urls = []
        patches = [
            patch('os.environ', dict(ENV)),
            patch('frontend.open', mock_open(read_data='foo')),
            patch('frontend.requests.get', side_effect=RequestException),
            patch('frontend.jwt.decode', return_value=TOKEN_DATA),
            patch('api_call.get', side_effect=self.fake_get),
        ]
        for started in patches:
            started.start()
            self.addCleanup(started.stop)
        self.client = frontend.create_app().test_client()
        self.client.set_cookie('token', 'abc')

    def fake_get(self, url, **_kwargs):
        """The faked backend: answers by the path of the URL"""
        self.urls.append(url)
        for path, resp in self.responses.items():
            if path in url:
                if isinstance(resp, Exception):
                    raise resp
                return resp
        raise AssertionError(f'unexpected call to {url}')

    def home(self):
        """Fetch the home page and parse it"""
        resp = self.client.get('/home')
        self.assertEqual(resp.status_code, 200)
        return resp.get_data(as_text=True)

    def spending_rows(self, page):
        """(month, label, amount) of every spending row on the page"""
        rows = []
        for month in re.findall(r'<div class="spending-month".*?</table>', page, re.S):
            title = text_of(r'spending-month-title">(.*?)</h5>', month)
            for row in re.findall(r'<tr class="spending-row">.*?</tr>', month, re.S):
                rows.append((title,
                             text_of(r'spending-counterparty">(.*?)</td>', row),
                             text_of(r'spending-amount[^"]*">(.*?)</td>', row)))
        return rows


class TestSpendingSection(SpendingTestCase):
    """The summary is shown with labels, last 4 digits and dollars"""

    def test_asks_history_service_for_the_account(self):
        """the spending endpoint is called for the signed in account"""
        self.home()
        self.assertIn(f'http://history/spending/{ACCOUNT_ID}', self.urls)

    def test_rows_use_contact_label_or_last_four_digits(self):
        """a contact is shown by label, anyone else by their last 4 digits"""
        page = self.home()
        self.assertIn('id="spending-section"', page)
        self.assertIn('Spending by counterparty', page)
        self.assertEqual(self.spending_rows(page), [
            ('November 2026', 'Alice', '$1,234.56'),
            ('November 2026', 'account ending in 3333', '$0.05'),
            ('October 2026', 'account ending in 3333', '$20.00'),
        ])
        self.assertNotIn('id="spending-empty"', page)

    def test_contact_with_another_routing_number_is_not_matched(self):
        """the same account number at another bank is not the contact"""
        self.responses['/spending/'] = json_response([
            {'month': '2026-11', 'counterparties': [
                {'counterpartyAccountNum': '1111111111',
                 'counterpartyRoutingNum': '123456789', 'totalCents': 100}]}])
        page = self.home()
        self.assertEqual(self.spending_rows(page),
                         [('November 2026', 'account ending in 1111', '$1.00')])

    def test_contact_without_a_label_uses_last_four_digits(self):
        """a contact with no label falls back to the last 4 digits"""
        self.responses['/contacts/'] = json_response(
            [{'account_num': '1111111111', 'routing_num': LOCAL_ROUTING}])
        page = self.home()
        self.assertEqual(self.spending_rows(page)[0][1], 'account ending in 1111')

    def test_months_without_spending_are_skipped(self):
        """only months with spending get a block"""
        self.responses['/spending/'] = json_response([
            {'month': '2026-11', 'counterparties': []}, SPENDING[1]])
        page = self.home()
        self.assertEqual(self.spending_rows(page),
                         [('October 2026', 'account ending in 3333', '$20.00')])


class TestSpendingEmptyAndFailed(SpendingTestCase):
    """The page still loads when there is nothing to show"""

    def assert_empty_state(self, page, text):
        """the section shows one message and no rows"""
        self.assertEqual(text_of(r'id="spending-empty">(.*?)</h4>', page), text)
        self.assertEqual(self.spending_rows(page), [])
        # the rest of the page is still there
        self.assertIn('id="current-balance"', page)
        self.assertIn('id="transaction-table"', page)

    def test_no_spending_shows_empty_state(self):
        """both months empty gives the empty-state message"""
        self.responses['/spending/'] = json_response([
            {'month': '2026-11', 'counterparties': []},
            {'month': '2026-10', 'counterparties': []}])
        self.assert_empty_state(self.home(), 'No spending this month or last month')

    def test_empty_list_shows_empty_state(self):
        """an empty answer gives the empty-state message"""
        self.responses['/spending/'] = json_response([])
        self.assert_empty_state(self.home(), 'No spending this month or last month')

    def test_unreachable_service_shows_empty_state(self):
        """a failed call does not break the page"""
        self.responses['/spending/'] = RequestException('down')
        self.assert_empty_state(self.home(), 'Spending is unavailable right now')

    def test_error_status_shows_empty_state(self):
        """a 4xx/5xx answer does not break the page"""
        self.responses['/spending/'] = json_response('server error', ok=False)
        self.assert_empty_state(self.home(), 'Spending is unavailable right now')

    def test_unreadable_body_shows_empty_state(self):
        """a body that is not JSON does not break the page"""
        bad = json_response(None)
        bad.json.side_effect = ValueError('not json')
        self.responses['/spending/'] = bad
        self.assert_empty_state(self.home(), 'Spending is unavailable right now')

    def test_malformed_body_shows_empty_state(self):
        """JSON of an unexpected shape does not break the page"""
        self.responses['/spending/'] = json_response([{'month': '2026-11'}])
        self.assert_empty_state(self.home(), 'Spending is unavailable right now')


if __name__ == '__main__':
    unittest.main()
