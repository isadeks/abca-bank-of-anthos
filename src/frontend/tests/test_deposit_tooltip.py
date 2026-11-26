"""The Deposit Funds card has a tooltip; the Send Payment card does not."""

import os
import re
import unittest

TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'templates',
                        'index.html')


class TestDepositTooltip(unittest.TestCase):
    """Tooltip on the home page cards"""

    def setUp(self):
        with open(TEMPLATE, encoding='utf-8') as f:
            self.html = f.read()

    def _card(self, target):
        return re.search(r'<div class="card card-button[^>]*data-target="#%s"[^>]*>'
                         % target, self.html).group(0)

    def test_deposit_card_has_title(self):
        """deposit card carries the tooltip"""
        self.assertIn('title="Add money to your checking account"',
                      self._card('depositFunds'))

    def test_send_payment_card_unchanged(self):
        """send payment card has no title"""
        self.assertNotIn('title=', self._card('sendPayment'))
