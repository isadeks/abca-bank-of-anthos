"""
The Deposit card on the home page has a tooltip.
"""

import os
import re
import unittest

TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'templates',
                        'index.html')


class TestDepositTooltip(unittest.TestCase):
    """The deposit card carries a title tooltip"""

    def test_card_has_tooltip(self):
        """the deposit card has the tooltip text"""
        with open(TEMPLATE, encoding='utf-8') as f:
            html = f.read()
        self.assertRegex(
            html,
            r'<div id="deposit-card" title="Add money to your checking account"')
        self.assertIsNotNone(re.search(r'data-target="#depositFunds"', html))
