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
Tests for the due date calculation and the payment ids of the runner.
"""

import datetime
import unittest

from worker import add_months, next_due_date, payment_id

D = datetime.date
PINNED = "3e14ef1e-d6f3-5ab3-8e00-9643b8f8da36"


class TestNextDueDate(unittest.TestCase):
    """The date after a due date"""

    def test_weekly_is_seven_days_later(self):
        """also across month and year ends"""
        for due, expected in ((D(2026, 3, 2), D(2026, 3, 9)),
                              (D(2026, 3, 28), D(2026, 4, 4)),
                              (D(2026, 12, 28), D(2027, 1, 4)),
                              (D(2028, 2, 24), D(2028, 3, 2))):
            with self.subTest(due=due):
                self.assertEqual(next_due_date(due, "weekly", due.day), expected)

    def test_monthly_keeps_the_day_of_the_month(self):
        """the same day, one month later"""
        for due, expected in ((D(2026, 1, 15), D(2026, 2, 15)),
                              (D(2026, 11, 15), D(2026, 12, 15)),
                              (D(2026, 12, 15), D(2027, 1, 15))):
            with self.subTest(due=due):
                self.assertEqual(next_due_date(due, "monthly", 15), expected)

    def test_monthly_clamps_to_the_end_of_a_short_month(self):
        """the 31st becomes the last day of a shorter month"""
        for due, expected in ((D(2026, 1, 31), D(2026, 2, 28)),
                              (D(2028, 1, 31), D(2028, 2, 29)),   # leap year
                              (D(2026, 3, 31), D(2026, 4, 30)),
                              (D(2026, 5, 30), D(2026, 6, 30))):
            with self.subTest(due=due):
                self.assertEqual(next_due_date(due, "monthly", 31), expected)

    def test_monthly_returns_to_the_anchor_day(self):
        """no drift: Jan 31, Feb 28, Mar 31, Apr 30, May 31"""
        due, seen = D(2026, 1, 31), []
        for _ in range(4):
            due = next_due_date(due, "monthly", 31)
            seen.append(due)
        self.assertEqual(seen, [D(2026, 2, 28), D(2026, 3, 31),
                                D(2026, 4, 30), D(2026, 5, 31)])

    def test_a_full_year_of_months(self):
        """twelve months later is the same day next year"""
        due = D(2026, 6, 10)
        for _ in range(12):
            due = next_due_date(due, "monthly", 10)
        self.assertEqual(due, D(2027, 6, 10))

    def test_unknown_frequency(self):
        """a frequency that is not weekly or monthly is an error"""
        with self.assertRaises(ValueError):
            next_due_date(D(2026, 1, 1), "daily", 1)

    def test_add_months(self):
        """months can be added across years"""
        self.assertEqual(add_months(D(2026, 11, 30), 3, 30), D(2027, 2, 28))


class TestPaymentId(unittest.TestCase):
    """The id of the payment of one due date"""

    def test_is_stable(self):
        """the same schedule and date always give the same id"""
        self.assertEqual(payment_id("abc", D(2026, 4, 7)),
                         payment_id("abc", D(2026, 4, 7)))
        # pinned: changing the id would make every running schedule pay its
        # current due date a second time
        self.assertEqual(payment_id("abc", D(2026, 4, 7)), PINNED)

    def test_differs_by_schedule_and_by_date(self):
        """another schedule or another date is another payment"""
        base = payment_id("abc", D(2026, 4, 7))
        self.assertNotEqual(base, payment_id("abd", D(2026, 4, 7)))
        self.assertNotEqual(base, payment_id("abc", D(2026, 4, 14)))

    def test_is_a_uuid(self):
        """the ledger takes any string, a UUID is what the web UI sends"""
        value = payment_id("abc", D(2026, 4, 7))
        self.assertRegex(value, r"^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}$")


if __name__ == "__main__":
    unittest.main()
