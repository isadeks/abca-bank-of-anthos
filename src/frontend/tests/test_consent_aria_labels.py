"""
The consent page's Approve and Deny buttons carry descriptive aria-labels.
"""

import os
import re
import unittest

TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'templates',
                        'consent.html')


class TestConsentAriaLabels(unittest.TestCase):
    """The consent template labels its buttons for assistive technology"""

    def setUp(self):
        with open(TEMPLATE, encoding='utf-8') as f:
            self.html = f.read()

    def test_approve_button(self):
        """Approve keeps its visible text and gets an aria-label"""
        self.assertRegex(
            self.html,
            r'<button[^>]*aria-label="Approve access for this app"[^>]*>Approve</button>')

    def test_deny_button(self):
        """Deny keeps its visible text and gets an aria-label"""
        self.assertRegex(
            self.html,
            r'<button[^>]*aria-label="Deny access for this app"[^>]*>Deny</button>')

    def test_only_two_labelled_buttons(self):
        """no other consent button is labelled"""
        self.assertEqual(len(re.findall(r'<button[^>]*aria-label=', self.html)), 2)
