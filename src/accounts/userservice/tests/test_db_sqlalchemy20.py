# Copyright 2024 Google LLC
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
Regression tests: UserDb uses only the SQLAlchemy 2.0 API (no legacy warnings)
and persists writes without relying on implicit autocommit.
"""

import unittest
import warnings

from sqlalchemy import text
from sqlalchemy.exc import SADeprecationWarning

from userservice.db import UserDb
from userservice.tests.constants import EXAMPLE_USER


class TestDbSqlAlchemy20(unittest.TestCase):
    """Test cases for SQLAlchemy 2.0 compatibility of UserDb"""

    def test_no_legacy_api_warnings(self):
        """UserDb construction and queries emit no SQLAlchemy 2.0 deprecation warnings"""
        with warnings.catch_warnings():
            warnings.simplefilter('error', SADeprecationWarning)
            db = UserDb('sqlite:///:memory:')
            db.users_table.create(db.engine)
            user = EXAMPLE_USER.copy()
            user['username'] = 'warnfree'
            user['accountid'] = '1'
            db.add_user(user)
            self.assertEqual(user, db.get_user('warnfree'))
            self.assertIsNotNone(db.generate_accountid())

    def test_metadata_is_not_bound(self):
        """The table metadata is not bound to an engine"""
        db = UserDb('sqlite:///:memory:')
        self.assertIsNone(getattr(db.users_table.metadata, 'bind', None))

    def test_add_user_is_committed(self):
        """A user added through add_user is visible from another connection"""
        db = UserDb('sqlite:///:memory:')
        db.users_table.create(db.engine)
        user = EXAMPLE_USER.copy()
        user['username'] = 'committed'
        user['accountid'] = '2'
        db.add_user(user)
        with db.engine.connect() as conn:
            count = conn.execute(text('SELECT COUNT(*) FROM users')).scalar()
        self.assertEqual(1, count)
