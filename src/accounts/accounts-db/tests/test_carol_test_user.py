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

"""Checks the extra demo user 'carol' is seeded in both databases."""

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ACCOUNTS = REPO / 'src' / 'accounts' / 'accounts-db' / 'initdb'
LEDGER = REPO / 'src' / 'ledger' / 'ledger-db' / 'initdb' / '1_create_transactions.sh'


class CarolTestUserTest(unittest.TestCase):
    def test_user_script_adds_carol_and_contacts(self):
        text = (ACCOUNTS / '1-load-testdata.sh').read_text()
        self.assertIn('add_user "1099887766" "carol" "Carol"', text)
        for owner in ('testuser', 'alice', 'bob', 'eve'):
            self.assertIn('add_contact "%s" "Carol" "1099887766"' % owner, text)
        self.assertIn('add_contact "carol" "Testuser" "1011226111"', text)

    def test_sql_adds_carol(self):
        text = (ACCOUNTS / '1-load-testdata.sql').read_text()
        self.assertIn("('1099887766', 'carol',", text)
        self.assertIn("('testuser', 'Carol', '1099887766'", text)

    def test_ledger_seeds_carol_account(self):
        self.assertIn('"1099887766"', LEDGER.read_text())


if __name__ == '__main__':
    unittest.main()
