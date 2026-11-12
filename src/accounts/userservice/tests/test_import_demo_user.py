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
Tests for the one-off import of an accounts-db user into Cognito
"""

import unittest

import cognito_auth
from userservice.db import UserDb
from userservice.tests.constants import EXAMPLE_USER
from userservice.tests.fake_cognito import FakeCognitoClient
from userservice.tools.import_demo_user import import_user


class TestImportDemoUser(unittest.TestCase):
    """
    Test cases for tools/import_demo_user.py
    """

    def setUp(self):
        self.cognito = FakeCognitoClient()
        self.auth = cognito_auth.CognitoAuth('pool', 'client', 'eu-west-1', client=self.cognito)
        self.db = UserDb('sqlite:///:memory:')
        self.db.users_table.create(self.db.engine)
        user = EXAMPLE_USER.copy()
        user.update(username='testuser', accountid='1011226111',
                    firstname='Test', lastname='User')
        self.db.add_user(user)

    def test_imports_user_with_account_id_and_name(self):
        """the user can log in, and carries its existing account id and name"""
        self.assertEqual('created',
                         import_user(self.db, self.auth, 'testuser', 'bankofanthos'))
        self.assertEqual('id-token-for-testuser',
                         self.auth.authenticate('testuser', 'bankofanthos'))
        attributes = self.cognito.users['testuser']['attributes']
        self.assertEqual('1011226111', attributes['custom:acct'])
        self.assertEqual('Test User', attributes['name'])

    def test_second_run_changes_nothing(self):
        """importing a user that is already in the pool is not an error"""
        import_user(self.db, self.auth, 'testuser', 'bankofanthos')
        self.assertEqual('exists',
                         import_user(self.db, self.auth, 'testuser', 'another-password'))
        self.assertEqual('bankofanthos', self.cognito.users['testuser']['password'])

    def test_unknown_accounts_db_user_is_an_error(self):
        """only users of the accounts database can be imported"""
        with self.assertRaises(LookupError):
            import_user(self.db, self.auth, 'ghost', 'bankofanthos')
        self.assertEqual({}, {k: v for k, v in self.cognito.users.items() if k == 'ghost'})
