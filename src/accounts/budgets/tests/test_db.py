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
Tests for db module
"""

import unittest

from budgets.db import BudgetsDb


class TestDb(unittest.TestCase):
    """
    Test cases for db module
    """

    def setUp(self):
        """Init db with sqlite in mem and create the table like the service does"""
        self.db = BudgetsDb("sqlite:///:memory:")
        self.db.create_table()

    def test_create_table_twice_is_harmless(self):
        """the table is created only if missing, so a restart keeps the data"""
        self.db.set_budget("foo", 1000)
        self.db.create_table()
        self.assertEqual(self.db.get_budget("foo"), 1000)

    def test_get_budget_none_when_not_set(self):
        """a user without a budget has no limit"""
        self.assertIsNone(self.db.get_budget("foo"))

    def test_set_budget_then_get(self):
        """a stored limit is returned in whole cents"""
        self.db.set_budget("foo", 12345)
        self.assertEqual(self.db.get_budget("foo"), 12345)

    def test_set_budget_twice_updates(self):
        """setting again replaces the limit, keeping one row per user"""
        self.db.set_budget("foo", 1000)
        self.db.set_budget("foo", 2000)
        self.assertEqual(self.db.get_budget("foo"), 2000)

    def test_budgets_are_per_user(self):
        """one user's limit does not leak to another"""
        self.db.set_budget("foo", 1000)
        self.db.set_budget("bar", 2000)
        self.assertEqual(self.db.get_budget("foo"), 1000)
        self.assertEqual(self.db.get_budget("bar"), 2000)
        self.assertIsNone(self.db.get_budget("baz"))

    def test_clear_budget_removes_only_that_users_limit(self):
        """clearing deletes the limit; clearing again is harmless"""
        self.db.set_budget("foo", 1000)
        self.db.set_budget("bar", 2000)
        self.db.clear_budget("foo")
        self.db.clear_budget("foo")
        self.assertIsNone(self.db.get_budget("foo"))
        self.assertEqual(self.db.get_budget("bar"), 2000)
