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
Tests for savings accounts: the UserDb helpers and the userservice endpoints
"""

import unittest
from unittest.mock import patch, mock_open

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from userservice.db import UserDb
from userservice.userservice import create_app
from userservice.tests.constants import EXAMPLE_USER


class TestSavingsDb(unittest.TestCase):
    """Test cases for the savings account helpers of UserDb"""

    def setUp(self):
        """Init db and create the users table before each test"""
        self.db = UserDb('sqlite:///:memory:')
        self.db.users_table.create(self.db.engine)

    def test_no_savings_account_by_default(self):
        """a user without a savings account gets None (table created on demand)"""
        self.assertIsNone(self.db.get_savings_account('foo'))

    def test_add_and_get_savings_account(self):
        """an added savings account is returned for its owner only"""
        self.db.add_savings_account('foo', '42')
        self.assertEqual(self.db.get_savings_account('foo'), '42')
        self.assertIsNone(self.db.get_savings_account('bar'))

    def test_one_savings_account_per_user(self):
        """a second savings account for the same user is rejected"""
        self.db.add_savings_account('foo', '42')
        with self.assertRaises(IntegrityError):
            self.db.add_savings_account('foo', '43')

    @patch('random.randint', side_effect=[7, 8, 9])
    def test_generate_account_id_skips_savings_account_ids(self, _mock_rand):
        """a generated account id never collides with a savings account"""
        self.db.add_savings_account('foo', '7')
        user = EXAMPLE_USER.copy()
        user['accountid'] = '8'
        self.db.add_user(user)
        self.assertEqual(self.db.generate_accountid(), '9')


class TestSavingsEndpoints(unittest.TestCase):
    """Test cases for the savings account endpoints of userservice"""

    def setUp(self):
        """Setup Flask TestClient and mock userdatabase"""
        with patch('userservice.userservice.open', mock_open(read_data='foo')):
            with patch(
                'os.environ',
                {
                    'VERSION': '1',
                    'TOKEN_EXPIRY_SECONDS': '3600',
                    'PRIV_KEY_PATH': '1',
                    'PUB_KEY_PATH': '1',
                    'ENABLE_TRACING': 'false',
                },
            ):
                with patch('userservice.userservice.UserDb') as mock_db:
                    self.db = mock_db.return_value
                    flask_app = create_app()
                    flask_app.config['TESTING'] = True
                    self.client = flask_app.test_client()

    def test_get_savings_account_returns_account_id(self):
        """an existing savings account is returned"""
        self.db.get_savings_account.return_value = '42'
        response = self.client.get('/users/foo/savings')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'accountid': '42'})

    def test_get_savings_account_missing_is_404(self):
        """a user without a savings account gets 404"""
        self.db.get_savings_account.return_value = None
        response = self.client.get('/users/foo/savings')
        self.assertEqual(response.status_code, 404)

    def test_get_savings_account_sql_error_is_500(self):
        """a database failure gives 500"""
        self.db.get_savings_account.side_effect = SQLAlchemyError()
        response = self.client.get('/users/foo/savings')
        self.assertEqual(response.status_code, 500)

    def test_create_savings_account_201_with_new_account_id(self):
        """opening a savings account stores and returns a generated id"""
        self.db.get_user.return_value = {'username': 'foo'}
        self.db.get_savings_account.return_value = None
        self.db.generate_accountid.return_value = '4242424242'
        response = self.client.post('/users/foo/savings')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json(), {'accountid': '4242424242'})
        self.db.add_savings_account.assert_called_once_with('foo', '4242424242')

    def test_create_savings_account_unknown_user_is_404(self):
        """only existing users can open a savings account"""
        self.db.get_user.return_value = None
        response = self.client.post('/users/ghost/savings')
        self.assertEqual(response.status_code, 404)
        self.db.add_savings_account.assert_not_called()

    def test_create_savings_account_twice_is_409(self):
        """a user with a savings account cannot open another"""
        self.db.get_user.return_value = {'username': 'foo'}
        self.db.get_savings_account.return_value = '42'
        response = self.client.post('/users/foo/savings')
        self.assertEqual(response.status_code, 409)
        self.db.add_savings_account.assert_not_called()

    def test_create_savings_account_race_is_409(self):
        """losing a race with a concurrent request gives 409, not 500"""
        self.db.get_user.return_value = {'username': 'foo'}
        self.db.get_savings_account.return_value = None
        self.db.generate_accountid.return_value = '4242424242'
        self.db.add_savings_account.side_effect = IntegrityError('x', {}, Exception())
        response = self.client.post('/users/foo/savings')
        self.assertEqual(response.status_code, 409)

    def test_create_savings_account_sql_error_is_500(self):
        """a database failure gives 500"""
        self.db.get_user.return_value = {'username': 'foo'}
        self.db.get_savings_account.return_value = None
        self.db.add_savings_account.side_effect = SQLAlchemyError()
        response = self.client.post('/users/foo/savings')
        self.assertEqual(response.status_code, 500)
