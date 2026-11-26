"""The Cymbal logo link has a tooltip and the logo image has alt text."""
import os
import unittest

import jinja2

FRONTEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestLogoTooltip(unittest.TestCase):
    def render(self, cymbal_logo):
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(os.path.join(FRONTEND, 'templates')))
        return env.get_template('shared/navigation.html').render(
            cymbal_logo=cymbal_logo, bank_name='Bank', name=None)

    def test_logo_link_has_title_and_alt(self):
        html = self.render('true')
        self.assertIn('title="Go to your home page"', html)
        self.assertIn('alt="Cymbal Bank"', html)

    def test_no_logo_no_tooltip(self):
        self.assertNotIn('Go to your home page', self.render('false'))
