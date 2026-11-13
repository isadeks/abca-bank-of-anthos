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

"""Checks that the accounts-db schema has the table of a user's additional accounts."""

import re
import unittest
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / 'initdb' / '0-accounts-schema.sql'


def table_definition(sql, name):
    """The column list of CREATE TABLE IF NOT EXISTS <name> (...)"""
    match = re.search(rf'CREATE TABLE IF NOT EXISTS {name} \((.*?)\n\);', sql, re.S)
    if match is None:
        raise AssertionError(f'no table {name} in {SCHEMA}')
    return match.group(1)


class TestAccountsTable(unittest.TestCase):
    """Users can have more than the account they signed up with"""

    def setUp(self):
        self.sql = SCHEMA.read_text()
        self.table = table_definition(self.sql, 'accounts')

    def test_account_number_is_the_primary_key(self):
        """each additional account has its own unique 10 digit number"""
        self.assertRegex(self.table, r'accountid CHAR\(10\) PRIMARY KEY')

    def test_account_belongs_to_a_user(self):
        """accounts reference their owner and go away with the user"""
        self.assertRegex(
            self.table,
            r'username VARCHAR\(64\) NOT NULL REFERENCES users\(username\) ON DELETE CASCADE')

    def test_account_has_a_label(self):
        """accounts are told apart by a label of at most 30 characters"""
        self.assertRegex(self.table, r'label VARCHAR\(30\) NOT NULL')

    def test_accounts_are_indexed_by_username(self):
        """listing a user's accounts uses an index"""
        self.assertIn('CREATE INDEX IF NOT EXISTS idx_accounts_username ON accounts (username)',
                      self.sql)

    def test_signup_account_stays_in_users(self):
        """the sign-up account is still a column of users"""
        self.assertRegex(table_definition(self.sql, 'users'), r'accountid CHAR\(10\) PRIMARY KEY')
