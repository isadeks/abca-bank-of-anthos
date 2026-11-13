# Copyright 2019 Google LLC
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
Tests for a user's multiple accounts: the account switcher on the home page,
opening and switching accounts, and transfers between a user's own accounts.
"""

import time
from unittest.mock import patch

import requests
from requests.exceptions import ConnectionError as RequestsConnectionError

import frontend
from test_payment_deposit_handlers import (
    LOCAL_ROUTING,
    ACCOUNT_ID, HandlerTestCase, TOKEN_DATA, backend_response)

SAVINGS_ID = '2222222222'
ACCOUNTS = [
    {'accountid': ACCOUNT_ID, 'label': 'Checking', 'is_primary': True},
    {'accountid': SAVINGS_ID, 'label': 'Savings', 'is_primary': False},
]


def json_response(body, status_code=200):
    """A fake backend response with a JSON body"""
    resp = backend_response(status_code, str(body))
    resp.json.return_value = body
    return resp


class AccountsTestCase(HandlerTestCase):
    """Home page backends answer from a table; the userservice is mocked"""

    def setUp(self):
        super().setUp()
        self.home_data = {
            frontend.BALANCE_NAME: 12345,
            frontend.TRANSACTION_LIST_NAME: [],
            frontend.CONTACTS_NAME: [],
            frontend.ACCOUNTS_NAME: ACCOUNTS,
        }

        def make_call(api_call):
            data = self.home_data[api_call.display_name]
            return None if data is None else json_response(data)

        patch('frontend.ApiCall.make_call', new=make_call).start()
        self.get = patch('frontend.requests.get',
                         return_value=json_response(ACCOUNTS)).start()

    def home(self):
        """Render the home page"""
        return self.client.get('/home')

    def accounts_calls(self):
        """The mocked posts that went to the userservice accounts endpoints"""
        uri = self.app.config['ACCOUNTS_URI']
        return [c for c in self.post.call_args_list if c.kwargs['url'].startswith(uri)]

    def transfer(self, **overrides):
        """Submit a transfer from the current account to Savings"""
        form = {'to_account': SAVINGS_ID, 'amount': '10', 'uuid': 'u3'}
        form.update(overrides)
        return self.client.post('/transfer', data=form)


class TestAccountSwitcher(AccountsTestCase):
    """The home page shows the accounts of the user"""

    def test_switcher_lists_accounts_and_marks_the_active_one(self):
        """each account is an option in the header; the active one is shown"""
        html = self.home().get_data(as_text=True)
        self.assertIn('id="account-switcher"', html)
        self.assertIn(f'value="{ACCOUNT_ID}"', html)
        self.assertIn(f'value="{SAVINGS_ID}"', html)
        self.assertIn('Open a new account', html)
        self.assertIn('<h2 class="header-title" id="account-title">Checking Account</h2>', html)

    def test_active_account_label_names_the_page(self):
        """when the token is for Savings, the page is titled Savings Account"""
        with patch('frontend.jwt.decode', return_value=dict(TOKEN_DATA, acct=SAVINGS_ID)):
            html = self.home().get_data(as_text=True)
        self.assertIn('id="account-title">Savings Account</h2>', html)
        self.assertIn(SAVINGS_ID, html)

    def test_transfer_offered_with_more_than_one_account(self):
        """the transfer form lists the other accounts only"""
        html = self.home().get_data(as_text=True)
        self.assertIn('id="transfer-form"', html)
        self.assertIn(f'<option value="{SAVINGS_ID}">Savings - {SAVINGS_ID}</option>', html)
        self.assertNotIn(f'<option value="{ACCOUNT_ID}">', html)

    def test_transfer_not_offered_with_a_single_account(self):
        """a user with only the sign-up account can open one but not transfer"""
        self.home_data[frontend.ACCOUNTS_NAME] = ACCOUNTS[:1]
        html = self.home().get_data(as_text=True)
        self.assertNotIn('id="transfer-form"', html)
        self.assertIn('id="open-account-form"', html)

    def test_page_works_when_accounts_cannot_be_loaded(self):
        """without the accounts list there is no switcher but the page renders"""
        self.home_data[frontend.ACCOUNTS_NAME] = None
        resp = self.home()
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('id="account-switcher"', html)
        self.assertIn('id="account-title">Checking Account</h2>', html)

    def test_history_labels_own_accounts(self):
        """a transfer to Savings shows Savings as the label"""
        self.home_data[frontend.TRANSACTION_LIST_NAME] = [{
            'fromAccountNum': ACCOUNT_ID, 'toAccountNum': SAVINGS_ID,
            'amount': 1000, 'timestamp': '2024-01-02T03:04:05.000+0000'}]
        html = self.home().get_data(as_text=True)
        label = html.split('transaction-label">')[1].split('</td>')[0]
        self.assertEqual(label.strip(), 'Savings')


class TestOpenAccount(AccountsTestCase):
    """/accounts"""

    def open_account(self, label='Savings'):
        """Submit the open account form"""
        return self.client.post('/accounts', data={'label': label})

    def test_without_token_is_unauthorized(self):
        """no token cookie gives 401 and nothing is sent"""
        self.client.delete_cookie('token')
        self.assertEqual(self.open_account().status_code, 401)
        self.post.assert_not_called()

    def test_success_switches_to_the_new_account(self):
        """the account is created, then a token for it replaces the cookie"""
        future = int(time.time()) + 600
        self.post.side_effect = [
            json_response({'accountid': SAVINGS_ID, 'label': 'Savings'}, 201),
            json_response({'token': 'new-token'}),
        ]
        with patch('frontend.jwt.decode',
                   return_value=dict(TOKEN_DATA, acct=SAVINGS_ID, exp=future)):
            resp = self.open_account()
        self.assertEqual(resp.status_code, 303)
        self.assertIn('msg=Opened+account+Savings', resp.headers['Location'])
        self.assertIn('token=new-token', resp.headers['Set-Cookie'])
        create, switch = self.accounts_calls()
        self.assertEqual(create.kwargs['url'], f'{self.app.config["ACCOUNTS_URI"]}/testuser')
        self.assertEqual(create.kwargs['data'], {'label': 'Savings'})
        self.assertEqual(switch.kwargs['url'],
                         f'{self.app.config["ACCOUNTS_URI"]}/testuser/token')
        self.assertEqual(switch.kwargs['data'], {'accountid': SAVINGS_ID})
        self.assertEqual(create.kwargs['headers']['Authorization'], 'Bearer abc')

    def test_rejected_label_shows_the_reason(self):
        """a 4xx from userservice gives 400 and its message on the page"""
        self.post.return_value = backend_response(
            409, 'an account with that label already exists')
        resp = self.open_account()
        self.assertEqual(resp.status_code, 400)
        html = resp.get_data(as_text=True)
        self.assertIn('Could not open account: an account with that label already exists', html)

    def test_userservice_failure_is_bad_gateway(self):
        """an unreachable userservice gives 502"""
        self.post.side_effect = RequestsConnectionError
        resp = self.open_account()
        self.assertEqual(resp.status_code, 502)
        self.assertIn('Could not open account', resp.get_data(as_text=True))

    def test_account_is_kept_when_the_switch_fails(self):
        """if only the token request fails the user is told the account exists"""
        self.post.side_effect = [
            json_response({'accountid': SAVINGS_ID, 'label': 'Savings'}, 201),
            RequestsConnectionError(),
        ]
        resp = self.open_account()
        self.assertEqual(resp.status_code, 303)
        self.assertIn('msg=Opened+account+Savings', resp.headers['Location'])
        self.assertNotIn('Set-Cookie', resp.headers)


class TestSwitchAccount(AccountsTestCase):
    """/accounts/switch"""

    def switch(self, account_id=SAVINGS_ID):
        """Submit the account switcher"""
        return self.client.post('/accounts/switch', data={'accountid': account_id})

    def test_without_token_is_unauthorized(self):
        """no token cookie gives 401 and nothing is sent"""
        self.client.delete_cookie('token')
        self.assertEqual(self.switch().status_code, 401)
        self.post.assert_not_called()

    def test_success_sets_the_new_token_and_goes_home(self):
        """the cookie lives as long as the new token is valid"""
        future = int(time.time()) + 600
        self.post.return_value = json_response({'token': 'savings-token'})
        with patch('frontend.jwt.decode',
                   return_value=dict(TOKEN_DATA, acct=SAVINGS_ID, exp=future)):
            resp = self.switch()
        self.assertEqual(resp.status_code, 303)
        self.assertIn('/home', resp.headers['Location'])
        cookie = resp.headers['Set-Cookie']
        self.assertIn('token=savings-token', cookie)
        max_age = int(cookie.split('Max-Age=')[1].split(';')[0])
        self.assertTrue(500 < max_age <= 600)

    def test_unknown_account_is_refused(self):
        """userservice answering 404 gives 400 and no cookie"""
        refusal = backend_response(404, 'account does not exist')
        refusal.raise_for_status.side_effect = requests.exceptions.HTTPError(
            'not found', response=refusal)
        self.post.return_value = refusal
        resp = self.switch('9999999999')
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn('Set-Cookie', resp.headers)
        self.assertIn('Could not switch account', resp.get_data(as_text=True))

    def test_userservice_error_is_bad_gateway(self):
        """a failing userservice gives 502"""
        self.post.return_value = backend_response(500, 'boom')
        self.assertEqual(self.switch().status_code, 502)

    def test_unreachable_userservice_is_bad_gateway(self):
        """no answer from userservice gives 502"""
        self.post.side_effect = RequestsConnectionError
        self.assertEqual(self.switch().status_code, 502)


class TestTransfer(AccountsTestCase):
    """/transfer"""

    def test_without_token_is_unauthorized(self):
        """no token cookie gives 401 and nothing is sent"""
        self.client.delete_cookie('token')
        self.assertEqual(self.transfer().status_code, 401)
        self.post.assert_not_called()

    def test_success_moves_money_between_own_accounts(self):
        """the ledger gets a local transaction from the current to the other account"""
        resp = self.transfer(amount='12.34')
        self.assertEqual(resp.status_code, 303)
        self.assertIn('msg=Transfer+successful', resp.headers['Location'])
        (call,) = self.ledger_calls()
        self.assertEqual(self.sent(call), {
            'fromAccountNum': ACCOUNT_ID, 'fromRoutingNum': LOCAL_ROUTING,
            'toAccountNum': SAVINGS_ID, 'toRoutingNum': LOCAL_ROUTING,
            'amount': 1234, 'uuid': 'u3'})

    def test_account_of_someone_else_is_refused(self):
        """only accounts userservice lists for the user can be transferred to"""
        resp = self.transfer(to_account='9999999999')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('not one of your accounts', resp.get_data(as_text=True))
        self.assertEqual(self.ledger_calls(), [])

    def test_same_account_is_refused(self):
        """transferring to the current account is refused"""
        resp = self.transfer(to_account=ACCOUNT_ID)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('choose a different account', resp.get_data(as_text=True))
        self.assertEqual(self.ledger_calls(), [])

    def test_three_decimal_amount_is_refused(self):
        """amounts are exact to the cent, like deposits"""
        resp = self.transfer(amount='1.234')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.ledger_calls(), [])

    def test_insufficient_balance_is_reported(self):
        """a 400 from the ledger shows its message"""
        self.post.return_value = backend_response(400, 'insufficient balance')
        resp = self.transfer()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Transfer failed: insufficient balance', resp.get_data(as_text=True))

    def test_missing_field_is_refused(self):
        """a form without the target account is refused"""
        resp = self.client.post('/transfer', data={'amount': '1', 'uuid': 'u'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('missing form field', resp.get_data(as_text=True))

    def test_unreachable_userservice_is_bad_gateway(self):
        """if the accounts cannot be checked nothing is transferred"""
        self.get.side_effect = RequestsConnectionError
        resp = self.transfer()
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(self.ledger_calls(), [])
