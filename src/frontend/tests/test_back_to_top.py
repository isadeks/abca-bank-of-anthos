"""
The transaction history ends with a "Back to top" link.
"""

import os
import unittest

TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'templates',
                        'index.html')


class TestBackToTop(unittest.TestCase):
    """The home page template links back to the top after the rows"""

    def setUp(self):
        with open(TEMPLATE, encoding='utf-8') as f:
            self.html = f.read()

    def test_link_goes_to_top_of_page(self):
        """the link exists and points at the page top"""
        self.assertIn('id="back-to-top"', self.html)
        self.assertRegex(self.html,
                         r'<a id="back-to-top"[^>]*href="#"[^>]*>Back to top</a>')

    def test_link_follows_the_transaction_rows(self):
        """the link comes after the transaction table"""
        self.assertGreater(self.html.index('id="back-to-top"'),
                           self.html.index('id="transaction-list"'))
        self.assertGreater(self.html.index('id="back-to-top"'),
                           self.html.rindex('</table>', 0,
                                            self.html.index('id="back-to-top"')) - 1)
