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
Tests for login and signup through Cognito (with a mocked Cognito client)
"""

import unittest
from datetime import date
from unittest.mock import patch

from sqlalchemy.exc import OperationalError

import cognito_auth
from userservice.db import UserDb
from userservice.tests.constants import EXAMPLE_USER_REQUEST
from userservice.tests.fake_cognito import FakeCognitoClient
from userservice.userservice import create_app

PASSWORD = 'correct-horse-battery'


def signup_form(**overrides):
    """A valid sign-up form with a Cognito-acceptable password"""
    form = dict(EXAMPLE_USER_REQUEST, password=PASSWORD)
    form['password-repeat'] = form['password']
    form.update(overrides)
    return form


class TestCognitoLoginAndSignup(unittest.TestCase):
    """
    Test cases for the /login and /users endpoints backed by Cognito
    """

    def setUp(self):
        """Create the app on an in-memory database and a fake Cognito"""
        self.cognito = FakeCognitoClient()
        self.db = UserDb('sqlite:///:memory:')
        self.db.users_table.create(self.db.engine)
        # SQLite wants a date object where Postgres accepts the form's string
        add_user = self.db.add_user
        self.db.add_user = lambda user: add_user(
            dict(user, birthday=date.fromisoformat(user['birthday'])))
        env = {
            'ENABLE_TRACING': 'false',
            'ACCOUNTS_DB_URI': 'sqlite:///:memory:',
            'COGNITO_USER_POOL_ID': 'pool-id',
            'COGNITO_APP_CLIENT_ID': 'client-id',
            'COGNITO_REGION': 'eu-west-1',
        }
        auth = cognito_auth.CognitoAuth('pool-id', 'client-id', 'eu-west-1',
                                        client=self.cognito)
        with patch.dict('os.environ', env), \
                patch('userservice.userservice.UserDb', return_value=self.db), \
                patch.object(cognito_auth.CognitoAuth, 'from_env', return_value=auth):
            app = create_app()
        self.client = app.test_client()

    def _signup(self, **overrides):
        return self.client.post('/users', data=signup_form(**overrides))

    def test_signup_creates_cognito_user_and_profile(self):
        """signup stores credentials in Cognito and the profile in the database"""
        response = self._signup()
        self.assertEqual(201, response.status_code)

        stored = self.db.get_user('jdoe')
        self.assertEqual('John', stored['firstname'])
        self.assertEqual(10, len(stored['accountid']))
        # the password is not kept in the accounts database
        self.assertEqual(b'', bytes(stored['passhash']))

        cognito_user = self.cognito.users['jdoe']
        self.assertEqual(PASSWORD, cognito_user['password'])
        # the account id and display name travel as token claims
        self.assertEqual(stored['accountid'], cognito_user['attributes']['custom:acct'])
        self.assertEqual('John Doe', cognito_user['attributes']['name'])

    def test_login_success_returns_cognito_id_token(self):
        """login returns the ID token Cognito issued"""
        self._signup()
        response = self.client.get(
            '/login', query_string={'username': 'jdoe', 'password': PASSWORD})
        self.assertEqual(200, response.status_code)
        self.assertEqual({'token': 'id-token-for-jdoe'}, response.get_json())

    def test_login_wrong_password_is_unauthorized(self):
        """a wrong password is a 401"""
        self._signup()
        response = self.client.get(
            '/login', query_string={'username': 'jdoe', 'password': 'not-the-password'})
        self.assertEqual(401, response.status_code)
        self.assertNotIn('token', response.get_data(as_text=True))

    def test_login_unknown_user_is_not_found(self):
        """a user that is not in the pool is a 404"""
        response = self.client.get(
            '/login', query_string={'username': 'nobody', 'password': PASSWORD})
        self.assertEqual(404, response.status_code)

    def test_login_without_credentials_is_not_found(self):
        """missing query parameters do not crash the service"""
        response = self.client.get('/login')
        self.assertEqual(404, response.status_code)

    def test_signup_duplicate_in_cognito_is_conflict(self):
        """a username that exists in the pool but not the database is a 409"""
        self.cognito.users['jdoe'] = {'password': 'x' * 8, 'attributes': {}}
        response = self._signup()
        self.assertEqual(409, response.status_code)
        self.assertIsNone(self.db.get_user('jdoe'))

    def test_signup_duplicate_user_is_conflict(self):
        """signing up twice with the same username is a 409"""
        self.assertEqual(201, self._signup().status_code)
        again = self._signup()
        self.assertEqual(409, again.status_code)
        self.assertEqual(1, len(self.cognito.users))

    def test_signup_weak_password_is_bad_request(self):
        """a password the pool rejects is a 400 and leaves nothing behind"""
        response = self._signup(password='abc', **{'password-repeat': 'abc'})
        self.assertEqual(400, response.status_code)
        self.assertEqual({}, self.cognito.users)
        self.assertIsNone(self.db.get_user('jdoe'))

    def test_signup_database_failure_removes_cognito_user(self):
        """if the profile cannot be stored, the Cognito user is removed again"""
        with patch.object(self.db, 'add_user',
                          side_effect=OperationalError('insert', {}, Exception('down'))):
            response = self._signup()
        self.assertEqual(500, response.status_code)
        self.assertEqual({}, self.cognito.users)


class TestCognitoNotConfigured(unittest.TestCase):
    """
    Test cases for a service started without the Cognito environment variables
    """

    def test_login_and_signup_fail_with_server_error(self):
        """the service stays up but cannot sign anyone in or up"""
        env = {'ENABLE_TRACING': 'false', 'ACCOUNTS_DB_URI': 'sqlite:///:memory:'}
        with patch.dict('os.environ', env, clear=True), \
                patch('userservice.userservice.UserDb') as mock_db:
            mock_db.return_value.get_user.return_value = None
            client = create_app().test_client()
        self.assertEqual(200, client.get('/ready').status_code)
        self.assertEqual(500, client.get(
            '/login', query_string={'username': 'jdoe', 'password': PASSWORD}).status_code)
        self.assertEqual(500, client.post('/users', data=signup_form()).status_code)


class TestCognitoAuth(unittest.TestCase):
    """
    Test cases for the CognitoAuth wrapper
    """

    def test_from_env_reads_pool_client_and_region(self):
        """configuration comes from environment variables"""
        with patch('cognito_auth.boto3.client') as make_client:
            auth = cognito_auth.CognitoAuth.from_env({
                'COGNITO_USER_POOL_ID': 'pool',
                'COGNITO_APP_CLIENT_ID': 'client',
                'COGNITO_REGION': 'us-east-2',
            })
        make_client.assert_called_once_with('cognito-idp', region_name='us-east-2')
        self.assertEqual('pool', auth.user_pool_id)
        self.assertEqual('client', auth.client_id)

    def test_from_env_requires_the_pool_id(self):
        """a missing variable stops the service from starting"""
        with self.assertRaises(KeyError):
            cognito_auth.CognitoAuth.from_env({
                'COGNITO_APP_CLIENT_ID': 'client', 'COGNITO_REGION': 'us-east-2'})

    def test_authenticate_uses_password_flow_of_the_app_client(self):
        """the login call carries the client id and the credentials"""
        fake = FakeCognitoClient()
        auth = cognito_auth.CognitoAuth('pool', 'client', 'eu-west-1', client=fake)
        auth.create_user('jdoe', PASSWORD, '1234567890', 'John Doe')
        with patch.object(fake, 'initiate_auth', wraps=fake.initiate_auth) as spy:
            token = auth.authenticate('jdoe', PASSWORD)
        spy.assert_called_once_with(
            ClientId='client', AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={'USERNAME': 'jdoe', 'PASSWORD': PASSWORD})
        self.assertEqual('id-token-for-jdoe', token)

    def test_authenticate_challenge_is_not_a_login(self):
        """a challenge response without a token is rejected"""
        fake = FakeCognitoClient()
        auth = cognito_auth.CognitoAuth('pool', 'client', 'eu-west-1', client=fake)
        with patch.object(fake, 'initiate_auth',
                          return_value={'ChallengeName': 'NEW_PASSWORD_REQUIRED'}):
            with self.assertRaises(cognito_auth.InvalidCredentials):
                auth.authenticate('jdoe', PASSWORD)
