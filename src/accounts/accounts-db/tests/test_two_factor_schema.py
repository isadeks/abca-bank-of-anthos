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

"""The accounts-db schema has the table for optional two-factor sign-in."""

import unittest
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / 'initdb' / '0-accounts-schema.sql'


class TestTwoFactorSchema(unittest.TestCase):
    """user_totp keeps the secret encrypted and recovery codes hashed"""

    def setUp(self):
        self.sql = SCHEMA.read_text()

    def test_table_is_created_idempotently(self):
        """the table may already exist on an upgraded database"""
        self.assertIn('CREATE TABLE IF NOT EXISTS user_totp', self.sql)

    def test_columns(self):
        """the columns userservice's UserDb expects"""
        table = self.sql.split('user_totp (', 1)[1].split(');', 1)[0]
        for column in ('username', 'secret_enc BYTEA', 'enabled BOOLEAN',
                       'recovery_hashes', 'last_step', 'failed_attempts',
                       'locked_until'):
            self.assertIn(column, table)
        self.assertNotIn('secret VARCHAR', table)


if __name__ == '__main__':
    unittest.main()
