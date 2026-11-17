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

"""Checks that the accounts-db schema defines the currency_orders table."""

import unittest
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / 'initdb' / '0-accounts-schema.sql'


class TestCurrencyOrdersSchema(unittest.TestCase):
    """The frontend stores currency orders in accounts-db"""

    def test_table_is_created_idempotently(self):
        """the schema creates currency_orders only if missing"""
        sql = SCHEMA.read_text()
        self.assertIn('CREATE TABLE IF NOT EXISTS currency_orders', sql)

    def test_table_has_order_columns(self):
        """the columns the frontend reads and writes are present"""
        sql = SCHEMA.read_text()
        block = sql[sql.index('currency_orders'):]
        for column in ('order_id', 'username', 'currency', 'amount',
                       'customer_rate', 'total', 'address', 'status',
                       'placed_at'):
            self.assertIn(column, block)


if __name__ == '__main__':
    unittest.main()
