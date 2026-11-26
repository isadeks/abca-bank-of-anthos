"""
The deposit card is titled "Add money" (DEM-379).
"""

import os
import re
import unittest

TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'templates',
                        'index.html')


class TestAddMoneyTitle(unittest.TestCase):
    """The home page template titles the deposit card"""

    def setUp(self):
        with open(TEMPLATE, encoding='utf-8') as f:
            self.html = f.read()

    def test_title_is_add_money(self):
        """the deposit span reads Add money"""
        self.assertRegex(self.html,
                         r'id="depositSpan">\s*Add money\s*</span>')

    def test_old_title_is_gone(self):
        """Deposit Funds no longer appears"""
        self.assertIsNone(re.search('Deposit Funds', self.html))
