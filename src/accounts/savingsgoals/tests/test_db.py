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

"""Tests for GoalsDb on an in-memory SQLite database"""

import unittest
from unittest.mock import patch

from db import GoalsDb


class TestGoalsDb(unittest.TestCase):
    """GoalsDb create, list, credit and delete"""

    def setUp(self):
        patcher = patch("db.SQLAlchemyInstrumentor")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.db = GoalsDb("sqlite://")

    def test_add_and_list(self):
        """goals are listed per user with their own ledger account"""
        first = self.db.add_goal("a", "Trip", 5000)
        self.db.add_goal("a", "Car", 9000)
        self.db.add_goal("b", "Other", 100)
        goals = self.db.get_goals("a")
        self.assertEqual([g["name"] for g in goals], ["Trip", "Car"])
        self.assertEqual(goals[0]["saved"], 0)
        self.assertEqual(goals[0]["target"], 5000)
        self.assertRegex(first["account_num"], r"^7[0-9]{9}$")
        self.assertEqual(self.db.count_goals("a"), 2)
        self.assertNotEqual(goals[0]["account_num"], goals[1]["account_num"])

    def test_add_saved_accumulates(self):
        """contributions add up"""
        goal = self.db.add_goal("a", "Trip", 5000)
        self.db.add_saved("a", goal["id"], 1000)
        self.db.add_saved("a", goal["id"], 250)
        self.assertEqual(self.db.get_goal("a", goal["id"])["saved"], 1250)

    def test_other_users_cannot_touch_a_goal(self):
        """get, credit and delete are scoped to the owner"""
        goal = self.db.add_goal("a", "Trip", 5000)
        self.assertIsNone(self.db.get_goal("b", goal["id"]))
        self.db.add_saved("b", goal["id"], 100)
        self.assertFalse(self.db.delete_goal("b", goal["id"]))
        self.assertEqual(self.db.get_goal("a", goal["id"])["saved"], 0)

    def test_delete(self):
        """a deleted goal is gone"""
        goal = self.db.add_goal("a", "Trip", 5000)
        self.assertTrue(self.db.delete_goal("a", goal["id"]))
        self.assertEqual(self.db.get_goals("a"), [])
        self.assertFalse(self.db.delete_goal("a", goal["id"]))
