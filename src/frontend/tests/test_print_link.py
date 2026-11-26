"""
The home page has a Print link under Transaction History.
"""

import os
import re
import unittest

TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'templates',
                        'index.html')


class TestPrintLink(unittest.TestCase):
    """The home page template renders a Print link"""

    def test_print_link_rendered_under_heading(self):
        """The link has an id, calls window.print() and follows the heading"""
        with open(TEMPLATE, encoding='utf-8') as f:
            html = f.read()
        self.assertRegex(
            html,
            r'Transaction History\s*</h4>\s*<a id="print-link"[^>]*'
            r'window\.print\(\)[^>]*>Print</a>')
