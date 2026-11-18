"""Tests for filtering the transaction history by date."""

import unittest

from frontend import filter_transactions

ME = '1111111111'
HISTORY = [
    {'fromAccountNum': '2', 'toAccountNum': ME, 'timestamp': '2026-01-05T10:00:00.000000+0000'},
    {'fromAccountNum': ME, 'toAccountNum': '3', 'timestamp': '2026-02-10T10:00:00.000000+0000'},
    {'fromAccountNum': ME, 'toAccountNum': '4', 'timestamp': '2026-03-15T10:00:00.000000+0000'},
]


class TestDateFilter(unittest.TestCase):
    """filter_transactions narrows the list by date range"""

    def test_from(self):
        res = filter_transactions(HISTORY, ME, date_from='2026-02-10')
        self.assertEqual(res, HISTORY[1:])

    def test_to(self):
        res = filter_transactions(HISTORY, ME, date_to='2026-02-10')
        self.assertEqual(res, HISTORY[:2])

    def test_range_with_type(self):
        res = filter_transactions(HISTORY, ME, 'debit', '',
                                  '2026-02-01', '2026-02-28')
        self.assertEqual(res, [HISTORY[1]])

    def test_invalid_dates_ignored(self):
        res = filter_transactions(HISTORY, ME, date_from='garbage',
                                  date_to='2026-13-45')
        self.assertEqual(res, HISTORY)


if __name__ == '__main__':
    unittest.main()
