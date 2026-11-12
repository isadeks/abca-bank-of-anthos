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

"""Checks the scheduled payments tables of the accounts-db schema.

The schema is read as text (no database or SQL parser needed): each check looks at the
statement that creates a given table.
"""

import re
import unittest
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / 'initdb' / '0-accounts-schema.sql'


def create_statement(table):
    """The CREATE TABLE statement of `table`, comments removed."""
    sql = '\n'.join(re.sub(r'--.*$', '', line) for line in SCHEMA.read_text().splitlines())
    match = re.search(rf'CREATE TABLE IF NOT EXISTS {table} \((.*?)\n\);', sql, re.S)
    if not match:
        raise AssertionError(f'no CREATE TABLE IF NOT EXISTS {table} in {SCHEMA}')
    return match.group(1)


class ScheduledPaymentsSchemaTest(unittest.TestCase):
    """The tables behind the recurring payments"""

    def test_schedules_belong_to_a_user(self):
        statement = create_statement('scheduled_payments')
        self.assertIn('FOREIGN KEY (username) REFERENCES users(username)', statement)
        self.assertRegex(statement, r'schedule_id VARCHAR\(36\) PRIMARY KEY')

    def test_schedules_only_hold_valid_values(self):
        statement = create_statement('scheduled_payments')
        self.assertIn('CHECK (amount_cents > 0)', statement)
        self.assertIn("CHECK (frequency IN ('weekly', 'monthly'))", statement)
        self.assertIn("CHECK (status IN ('active', 'cancelled'))", statement)
        self.assertIn('CHECK (anchor_day BETWEEN 1 AND 31)', statement)
        self.assertRegex(statement, r'next_payment_date DATE NOT NULL')

    def test_a_due_date_can_only_be_attempted_once(self):
        """the primary key is what stops a due date from being paid twice"""
        statement = create_statement('scheduled_payment_attempts')
        self.assertIn('PRIMARY KEY (schedule_id, due_date)', statement)
        self.assertIn('REFERENCES scheduled_payments(schedule_id)', statement)
        self.assertIn("CHECK (status IN ('pending', 'succeeded', 'failed'))", statement)

    def test_schema_can_be_loaded_again(self):
        """every statement added for schedules is idempotent"""
        sql = SCHEMA.read_text()
        for statement in re.findall(r'^CREATE (?:UNIQUE )?(?:TABLE|INDEX) .*$', sql, re.M):
            self.assertIn('IF NOT EXISTS', statement)
        self.assertIn('idx_scheduled_payments_due', sql)


if __name__ == '__main__':
    unittest.main()
