"""Tests for the Larkspur Bank branding and theme."""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.dirname(HERE)


def _read(*parts):
    with open(os.path.join(FRONTEND, *parts), encoding='utf-8') as f:
        return f.read()


class TestBranding(unittest.TestCase):
    def test_default_bank_name(self):
        src = _read('frontend.py')
        self.assertNotIn('Bank of Anthos', src)
        self.assertGreaterEqual(src.count("'BANK_NAME', 'Larkspur Bank'"), 4)

    def test_theme_defined(self):
        css = _read('static', 'styles', 'cymbal.css')
        self.assertIn('--lb-navy', css)
        self.assertIn('Inter', css)

    def test_font_loaded(self):
        head = _read('templates', 'shared', 'html_head.html')
        self.assertTrue(re.search(r'family=Inter', head))


if __name__ == '__main__':
    unittest.main()
