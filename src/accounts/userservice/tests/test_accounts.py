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
Tests for userservice's multiple-accounts endpoints and the accounts table
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, mock_open

import jwt

from userservice.db import UserDb
from userservice.userservice import create_app
from userservice.tests.constants import (
    EXAMPLE_USER,
    EXAMPLE_PRIVATE_KEY,
    EXAMPLE_PUBLIC_KEY,
)

USERNAME = EXAMPLE_USER['username']
PRIMARY = EXAMPLE_USER['accountid']


def token_for(username=USERNAME, acct=PRIMARY, expires_in=3600):
    """A token signed with the example key, as login would issue it"""
    now = datetime.utcnow()
    payload = {'user': username, 'acct': acct, 'name': 'Test User',
               'iat': now, 'exp': now + timedelta(seconds=expires_in)}
    return jwt.encode(payload, EXAMPLE_PRIVATE_KEY, algorithm='RS256')


def bearer(token):
    """Authorization header carrying a token"""
    return {'Authorization': 'Bearer ' + token}


class TestAccountsEndpoints(unittest.TestCase):
    """Tests cases for the /accounts endpoints"""

    def setUp(self):
        with patch('userservice.userservice.open', mock_open(read_data='foo')):
            with patch('os.environ', {
                    'VERSION': '1',
                    'TOKEN_EXPIRY_SECONDS': '3600',
                    'PRIV_KEY_PATH': '1',
                    'PUB_KEY_PATH': '1',
                    'ENABLE_TRACING': 'false',
            }):
                with patch('userservice.userservice.UserDb') as mock_db:
                    self.db = mock_db.return_value
                    self.flask_app = create_app()
        self.flask_app.config['TESTING'] = True
        self.flask_app.config['PRIVATE_KEY'] = EXAMPLE_PRIVATE_KEY
        self.flask_app.config['PUBLIC_KEY'] = EXAMPLE_PUBLIC_KEY
        self.client = self.flask_app.test_client()
        self.db.get_user.return_value = EXAMPLE_USER.copy()
        self.db.get_accounts.return_value = []
        self.db.generate_accountid.return_value = '7777777777'

    def test_list_returns_signup_account_first(self):
        """The sign-up account is listed as the primary Checking account"""
        self.db.get_accounts.return_value = [{'accountid': '2222222222', 'label': 'Savings'}]
        response = self.client.get(f'/accounts/{USERNAME}', headers=bearer(token_for()))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [
            {'accountid': PRIMARY, 'label': 'Checking', 'is_primary': True},
            {'accountid': '2222222222', 'label': 'Savings', 'is_primary': False},
        ])

    def test_list_without_token_is_401(self):
        """Listing accounts needs a token"""
        self.assertEqual(self.client.get(f'/accounts/{USERNAME}').status_code, 401)

    def test_list_with_invalid_token_is_401(self):
        """A token that is not signed by userservice is refused"""
        response = self.client.get(f'/accounts/{USERNAME}', headers=bearer('garbage'))
        self.assertEqual(response.status_code, 401)

    def test_list_other_users_accounts_is_401(self):
        """A user cannot list someone else's accounts"""
        response = self.client.get('/accounts/alice', headers=bearer(token_for()))
        self.assertEqual(response.status_code, 401)
        self.db.get_accounts.assert_not_called()

    def test_create_account_201(self):
        """Opening an account stores it under a freshly generated number"""
        response = self.client.post(f'/accounts/{USERNAME}', data={'label': 'Savings'},
                                    headers=bearer(token_for()))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['accountid'], '7777777777')
        self.assertEqual(response.json['label'], 'Savings')
        self.db.add_account.assert_called_once_with(USERNAME, '7777777777', 'Savings')

    def test_create_account_invalid_label_400(self):
        """Labels follow the contact label rule"""
        for label in ('', '   ', 'x' * 31, 'bad*chars'):
            response = self.client.post(f'/accounts/{USERNAME}', data={'label': label},
                                        headers=bearer(token_for()))
            self.assertEqual(response.status_code, 400, label)
        self.db.add_account.assert_not_called()

    def test_create_account_duplicate_label_409(self):
        """Two accounts of a user cannot share a label, ignoring case"""
        for label in ('Savings', 'checking'):
            self.db.get_accounts.return_value = [{'accountid': '2222222222', 'label': 'Savings'}]
            response = self.client.post(f'/accounts/{USERNAME}', data={'label': label},
                                        headers=bearer(token_for()))
            self.assertEqual(response.status_code, 409, label)
        self.db.add_account.assert_not_called()

    def test_create_account_limit_400(self):
        """A user cannot open more than five accounts"""
        self.db.get_accounts.return_value = [
            {'accountid': str(i) * 10, 'label': f'Acct {i}'} for i in range(1, 5)]
        response = self.client.post(f'/accounts/{USERNAME}', data={'label': 'One too many'},
                                    headers=bearer(token_for()))
        self.assertEqual(response.status_code, 400)
        self.db.add_account.assert_not_called()

    def test_create_account_for_other_user_is_401(self):
        """A user cannot open accounts for someone else"""
        response = self.client.post('/accounts/alice', data={'label': 'Savings'},
                                    headers=bearer(token_for()))
        self.assertEqual(response.status_code, 401)
        self.db.add_account.assert_not_called()

    def test_switch_issues_token_for_the_other_account(self):
        """The new token acts on the chosen account and keeps the old expiry"""
        self.db.get_accounts.return_value = [{'accountid': '2222222222', 'label': 'Savings'}]
        old = token_for()
        old_claims = jwt.decode(old, EXAMPLE_PUBLIC_KEY, algorithms='RS256')
        response = self.client.post(f'/accounts/{USERNAME}/token',
                                    data={'accountid': '2222222222'}, headers=bearer(old))
        self.assertEqual(response.status_code, 200)
        claims = jwt.decode(response.json['token'], EXAMPLE_PUBLIC_KEY, algorithms='RS256')
        self.assertEqual(claims['acct'], '2222222222')
        self.assertEqual(claims['user'], USERNAME)
        self.assertEqual(claims['exp'], old_claims['exp'])
        self.assertEqual(claims['iat'], old_claims['iat'])

    def test_switch_back_to_signup_account(self):
        """The sign-up account can be switched to too"""
        self.db.get_accounts.return_value = [{'accountid': '2222222222', 'label': 'Savings'}]
        response = self.client.post(f'/accounts/{USERNAME}/token', data={'accountid': PRIMARY},
                                    headers=bearer(token_for(acct='2222222222')))
        self.assertEqual(response.status_code, 200)
        claims = jwt.decode(response.json['token'], EXAMPLE_PUBLIC_KEY, algorithms='RS256')
        self.assertEqual(claims['acct'], PRIMARY)

    def test_switch_to_someone_elses_account_is_404(self):
        """No token is issued for an account the user does not own"""
        response = self.client.post(f'/accounts/{USERNAME}/token',
                                    data={'accountid': '9999999999'},
                                    headers=bearer(token_for()))
        self.assertEqual(response.status_code, 404)

    def test_switch_without_token_is_401(self):
        """Switching needs a token"""
        response = self.client.post(f'/accounts/{USERNAME}/token',
                                    data={'accountid': PRIMARY})
        self.assertEqual(response.status_code, 401)


class TestAccountsDb(unittest.TestCase):
    """Tests cases for the accounts table helpers"""

    def setUp(self):
        self.db = UserDb('sqlite:///:memory:')
        self.db.users_table.create(self.db.engine, checkfirst=True)
        user = EXAMPLE_USER.copy()
        user['username'] = 'foo'
        user['accountid'] = '1111111111'
        self.db.add_user(user)

    def test_no_additional_accounts_by_default(self):
        """A user has no additional accounts until one is opened"""
        self.assertEqual(self.db.get_accounts('foo'), [])

    def test_added_account_is_listed_for_its_owner_only(self):
        """Accounts are listed per user"""
        self.db.add_account('foo', '2222222222', 'Savings')
        self.assertEqual(self.db.get_accounts('foo'),
                         [{'accountid': '2222222222', 'label': 'Savings'}])
        self.assertEqual(self.db.get_accounts('bar'), [])

    def test_generated_accountid_avoids_existing_accounts(self):
        """A generated number is never one that an additional account holds"""
        self.db.add_account('foo', '2222222222', 'Savings')
        with patch('userservice.db.random.randint',
                   side_effect=[2222222222, 3333333333]):
            self.assertEqual(self.db.generate_accountid(), '3333333333')
