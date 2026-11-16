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

"""Checks that the contacts table has the favourite flag and the demo data leaves it to the default."""

import re
import unittest
from pathlib import Path

INITDB = Path(__file__).resolve().parents[1] / 'initdb'


class TestFavoriteSchema(unittest.TestCase):
    """The is_favorite column of the contacts table"""

    def test_column_is_off_by_default(self):
        """existing contacts keep working: the column is NOT NULL DEFAULT FALSE"""
        schema = (INITDB / '0-accounts-schema.sql').read_text()
        self.assertRegex(schema, r'is_favorite BOOLEAN NOT NULL DEFAULT FALSE')

    def test_existing_databases_get_the_column(self):
        """an idempotent ALTER adds the column to a database created before"""
        schema = (INITDB / '0-accounts-schema.sql').read_text()
        self.assertRegex(
            schema, r'ALTER TABLE contacts ADD COLUMN IF NOT EXISTS is_favorite')

    def test_demo_inserts_name_their_columns(self):
        """demo contacts don't set the flag, so it defaults to off"""
        data = (INITDB / '1-load-testdata.sql').read_text()
        inserts = re.findall(r'INSERT INTO contacts[^\n]*', data)
        self.assertTrue(inserts)
        for line in inserts:
            self.assertIn('(username, label, account_num, routing_num, is_external)', line)


if __name__ == '__main__':
    unittest.main()
