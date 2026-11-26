"""
Login page demo-user help text and deposit amount hint.
"""

import os
import unittest

TEMPLATES = os.path.join(os.path.dirname(__file__), '..', 'templates')


def read(name):
    with open(os.path.join(TEMPLATES, name), encoding='utf-8') as f:
        return f.read()


class TestFormHints(unittest.TestCase):
    """Templates contain the requested hint lines"""

    def test_login_help_after_form(self):
        """demo users line sits below the login form"""
        html = read('login.html')
        self.assertIn('Demo users: alice, bob, eve (password bankofanthos)',
                      html)
        self.assertGreater(html.index('demo-users-help'),
                           html.index('</form>'))

    def test_deposit_amount_hint(self):
        """hint follows the deposit amount field"""
        html = read('index.html')
        self.assertIn('Amounts up to two decimal places', html)
        self.assertGreater(html.index('deposit-amount-hint'),
                           html.index('id="deposit-amount"'))
