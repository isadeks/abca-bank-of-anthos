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
Tests that the payment and deposit forms offer the 3 most recent payees and
external accounts as quick-pick chips.
"""

import re
import unittest
from unittest.mock import MagicMock, patch, mock_open

import frontend

LOCAL_ROUTING = '883745000'
EXTERNAL_ROUTING = '808889588'
ACCOUNT = '1234567890'
ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'LOCAL_ROUTING_NUM': LOCAL_ROUTING,
}
TOKEN_DATA = {'user': 'testuser', 'acct': ACCOUNT, 'name': 'Test'}


def trans(sender, recipient, from_routing=LOCAL_ROUTING, to_routing=LOCAL_ROUTING):
    """A transaction as returned by the transaction history service"""
    return {'fromAccountNum': sender, 'toAccountNum': recipient,
            'fromRoutingNum': from_routing, 'toRoutingNum': to_routing,
            'amount': 100, 'timestamp': '2026-01-01T00:00:00.000+00:00'}


def paid(recipient):
    """A payment from the user"""
    return trans(ACCOUNT, recipient)


def deposited(external):
    """A deposit from an external account into the user's account"""
    return trans(external, ACCOUNT, from_routing=EXTERNAL_ROUTING)


class TestRecentAccounts(unittest.TestCase):
    """The home page offers recent payees and external accounts as chips"""

    def setUp(self):
        patches = [
            patch.dict('os.environ', ENV),
            patch('frontend.open', mock_open(read_data='foo')),
            patch('frontend.jwt.decode', return_value=TOKEN_DATA),
        ]
        for started in patches:
            started.start()
            self.addCleanup(started.stop)
        self.history = []
        self.contacts = []
        self.client = frontend.create_app().test_client()
        self.client.set_cookie('token', 'abc')

    def home(self):
        """Render the home page with the configured history and contacts"""
        data = {'balance': 100000,
                'transaction_list': self.history,
                'contacts': self.contacts}

        def make_call(call):
            resp = MagicMock()
            resp.json.return_value = data[call.display_name]
            return resp

        with patch('frontend.ApiCall.make_call', autospec=True,
                   side_effect=make_call):
            resp = self.client.get('/home')
        self.assertEqual(resp.status_code, 200)
        return resp.get_data(as_text=True)

    @staticmethod
    def chips(body, section):
        """The account numbers of the chips in a section of the page"""
        block = re.search(r'id="%s".*?</div>' % section, body, re.S)
        if not block:
            return []
        return re.findall(r'data-account-num="(\d+)"', block.group(0))

    def test_no_history_shows_no_chips(self):
        """a new account has nothing to suggest"""
        body = self.home()
        self.assertNotIn('recent-payees', body)
        self.assertNotIn('recent-depositors', body)

    def test_payee_chips_are_the_three_most_recent_distinct(self):
        """newest first, one chip per payee, at most three"""
        self.history = [paid('1111111111'), paid('2222222222'),
                        paid('1111111111'), paid('3333333333'),
                        paid('4444444444')]
        self.assertEqual(self.chips(self.home(), 'recent-payees'),
                         ['1111111111', '2222222222', '3333333333'])

    def test_payee_chip_shows_contact_label(self):
        """a payee that is a contact is shown by its label"""
        self.history = [paid('1111111111')]
        self.contacts = [{'label': 'Alice', 'account_num': '1111111111',
                          'routing_num': LOCAL_ROUTING, 'is_external': False}]
        body = self.home()
        self.assertRegex(body, r'recent-chip"[^>]*data-label="Alice">Alice<')

    def test_payee_chips_ignore_deposits(self):
        """money received is not a payee"""
        self.history = [deposited('9099791699'), trans('5555555555', ACCOUNT)]
        body = self.home()
        self.assertNotIn('recent-payees', body)

    def test_deposit_chips_are_recent_external_accounts(self):
        """only external accounts that deposited are offered, with routing"""
        self.history = [paid('1111111111'),
                        trans('6666666666', ACCOUNT),
                        deposited('9099791699'),
                        deposited('9099791699'),
                        deposited('7777777777')]
        body = self.home()
        self.assertEqual(self.chips(body, 'recent-depositors'),
                         ['9099791699', '7777777777'])
        self.assertIn('data-routing-num="%s"' % EXTERNAL_ROUTING, body)
        self.assertEqual(self.chips(body, 'recent-payees'), ['1111111111'])

    def test_missing_history_shows_no_chips(self):
        """a failed history call does not break the page"""
        self.history = None
        body = self.home()
        self.assertNotIn('recent-chip"', body)


if __name__ == '__main__':
    unittest.main()
