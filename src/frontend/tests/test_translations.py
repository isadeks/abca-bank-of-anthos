# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Unit tests for the German translation of the UI and the language switch.
"""

import unittest

from test_payment_deposit_handlers import HandlerTestCase, backend_response
from translations import GERMAN, normalize_language, translate


class TestTranslate(unittest.TestCase):
    """The translation lookup"""

    def test_german_text(self):
        """a known text is translated"""
        self.assertEqual(translate('Sign in', 'de'), 'Anmelden')

    def test_english_and_unknown_unchanged(self):
        """English, unknown texts and non-strings are returned as they are"""
        self.assertEqual(translate('Sign in', 'en'), 'Sign in')
        self.assertEqual(translate('Something new', 'de'), 'Something new')
        self.assertIsNone(translate(None, 'de'))

    def test_detail_after_colon_is_kept(self):
        """only the part before the colon of a failure message is translated"""
        self.assertEqual(translate('Payment failed: no funds', 'de'),
                         'Zahlung fehlgeschlagen: no funds')

    def test_unsupported_language_falls_back(self):
        """an unknown language code is English"""
        self.assertEqual(normalize_language('fr'), 'en')
        self.assertEqual(normalize_language(None), 'en')
        self.assertEqual(normalize_language('de'), 'de')

    def test_no_empty_translations(self):
        """every German text is filled in"""
        for english, german in GERMAN.items():
            self.assertTrue(german.strip(), english)


class TestLanguageSwitch(HandlerTestCase):
    """The language cookie and the pages rendered with it"""

    def home(self):
        """the home page as html"""
        return self.client.get('/home').get_data(as_text=True)

    def test_default_is_english(self):
        """without a cookie the page is English"""
        html = self.home()
        self.assertIn('<html lang="en">', html)
        self.assertIn('Current Balance', html)
        self.assertNotIn('Aktueller Kontostand', html)

    def test_switch_to_german_sets_cookie_and_returns(self):
        """/language/de stores the choice and goes back to the page"""
        resp = self.client.get('/language/de',
                               headers={'Referer': 'http://localhost/home'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers['Location'], '/home')
        self.assertIn('language=de', resp.headers['Set-Cookie'])

    def test_german_home_page(self):
        """with the German cookie the home page is German"""
        self.client.set_cookie('language', 'de')
        html = self.home()
        self.assertIn('<html lang="de">', html)
        for text in ('Aktueller Kontostand', 'Geld einzahlen',
                     'Zahlung senden', 'Transaktionsverlauf', 'Abmelden'):
            self.assertIn(text, html)
        self.assertNotIn('Current Balance', html)

    def test_german_failure_message(self):
        """a failed payment shows the German message with the detail"""
        self.client.set_cookie('language', 'de')
        self.post.return_value = backend_response(400, 'nope')
        html = self.payment(account_num='add',
                            contact_account_num='7777777777',
                            contact_label='a' * 31).get_data(as_text=True)
        self.assertIn('Zahlung fehlgeschlagen', html)

    def test_german_login_page(self):
        """the login page is German too"""
        anonymous = self.app.test_client()
        anonymous.set_cookie('language', 'de')
        html = anonymous.get('/login').get_data(as_text=True)
        self.assertIn('ANMELDEN', html)
        self.assertIn('Konto erstellen', html)

    def test_unknown_language_is_404(self):
        """only supported languages can be chosen"""
        self.assertEqual(self.client.get('/language/xx').status_code, 404)

    def test_unsupported_cookie_is_english(self):
        """a cookie with an unsupported language is ignored"""
        self.client.set_cookie('language', 'xx')
        self.assertIn('Current Balance', self.home())

    def test_switcher_offers_both_languages(self):
        """the page links to the other language"""
        html = self.home()
        self.assertIn('href="/language/de"', html)
        self.client.set_cookie('language', 'de')
        self.assertIn('href="/language/en"', self.home())

    def test_foreign_referrer_is_not_followed(self):
        """the redirect never leaves this site"""
        resp = self.client.get('/language/de',
                               headers={'Referer': 'http://evil.example/x'})
        self.assertEqual(resp.headers['Location'], '/')
