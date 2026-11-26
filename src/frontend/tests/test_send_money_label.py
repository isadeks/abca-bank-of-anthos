import os
import unittest

ROOT = os.path.join(os.path.dirname(__file__), '..')


class SendMoneyLabelTest(unittest.TestCase):
    def test_label(self):
        with open(os.path.join(ROOT, 'templates', 'index.html')) as f:
            html = f.read()
        self.assertIn('>Send money</h3>', html)
        self.assertIn('Send money\n', html)
        self.assertNotIn('Send Payment\n', html)
        self.assertNotIn('Send a Payment', html)
