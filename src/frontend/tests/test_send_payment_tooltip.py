"""
The Send Payment card on the home page has a tooltip.
"""

import os
import re
import unittest

TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'templates',
                        'index.html')
TOOLTIP = 'Send money to a contact or another account'


class TestSendPaymentTooltip(unittest.TestCase):
    """The home page template puts the tooltip on the Send Payment card"""

    def test_tooltip_on_send_payment_card(self):
        """Done means 2: the card element carries the tooltip text"""
        with open(TEMPLATE, encoding='utf-8') as f:
            html = f.read()
        match = re.search(r'<div id="send-payment-card"[^>]*>', html)
        self.assertIsNotNone(match)
        self.assertIn('title="%s"' % TOOLTIP, match.group(0))
        self.assertIn('data-target="#sendPayment"', match.group(0))
