"""Tests for the community-bank look of the shared page parts."""
import os
import unittest

FRONTEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(FRONTEND, *parts), encoding='utf-8') as f:
        return f.read()


class TestBankLook(unittest.TestCase):
    def test_css_defines_bank_palette_and_serif(self):
        css = _read('static', 'styles', 'cymbal.css')
        self.assertIn('--cb-green', css)
        self.assertIn('--cb-gold', css)
        self.assertIn('Merriweather', css)

    def test_serif_font_loaded(self):
        self.assertIn('family=Merriweather',
                      _read('templates', 'shared', 'html_head.html'))

    def test_navigation_has_utility_bar_and_keeps_logout(self):
        nav = _read('templates', 'shared', 'navigation.html')
        self.assertIn('utility-bar', nav)
        self.assertIn('navbar-brand', nav)
        self.assertIn('logout-form', nav)

    def test_footer_has_links_without_copyright(self):
        footer = _read('templates', 'shared', 'footer.html')
        self.assertIn('footer-links', footer)
        self.assertNotIn('2020-2024', footer)
        self.assertNotIn('Google', footer)


if __name__ == '__main__':
    unittest.main()
