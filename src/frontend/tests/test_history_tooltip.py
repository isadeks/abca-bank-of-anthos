"""
The Transaction History heading has a tooltip.
"""

import os
import re
import unittest

TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'templates',
                        'index.html')


class TestHistoryTooltip(unittest.TestCase):
    """The home page template titles the Transaction History heading"""

    def test_heading_has_tooltip(self):
        """Done means 2: heading carries the tooltip title"""
        with open(TEMPLATE, encoding='utf-8') as f:
            html = f.read()
        self.assertRegex(
            html,
            r'<h4[^>]*title="Your last 10 transactions"[^>]*>\s*'
            r'Transaction History')
