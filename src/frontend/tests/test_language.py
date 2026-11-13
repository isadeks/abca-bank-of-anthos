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
The UI can be shown in French: chosen with ?lang=fr, remembered in a cookie,
or taken from the browser's Accept-Language header. English stays the default.
"""

import unittest

import i18n
from test_payment_deposit_handlers import HandlerTestCase


class TestI18n(unittest.TestCase):
    """The translation helpers"""

    def test_english_is_unchanged(self):
        """English returns the text itself"""
        self.assertEqual(i18n.translate('Deposit Funds', 'en'), 'Deposit Funds')

    def test_french_translation(self):
        """a known text is translated"""
        self.assertEqual(i18n.translate('Deposit Funds', 'fr'),
                         'Déposer des fonds')

    def test_unknown_text_is_unchanged(self):
        """a text without a translation is returned as is"""
        self.assertEqual(i18n.translate('Something new', 'fr'), 'Something new')

    def test_unknown_language_is_unchanged(self):
        """a language without translations returns the text itself"""
        self.assertEqual(i18n.translate('Sign out', 'de'), 'Sign out')

    def test_every_french_text_has_a_translation(self):
        """no translation is empty"""
        for english, french in i18n.FRENCH.items():
            self.assertTrue(french.strip(), english)

    def test_months(self):
        """month names follow the language"""
        self.assertEqual(i18n.month_abbreviation(2, 'en'), 'Feb')
        self.assertEqual(i18n.month_abbreviation(2, 'fr'), 'févr.')

    def test_choose_language_order(self):
        """?lang= beats the cookie, which beats the browser"""
        browser = [('fr-CA', 1)]
        self.assertEqual(i18n.choose_language('en', 'fr', browser), 'en')
        self.assertEqual(i18n.choose_language(None, 'en', browser), 'en')
        self.assertEqual(i18n.choose_language(None, None, browser), 'fr')

    def test_choose_language_ignores_unsupported(self):
        """an unsupported language falls through to the next choice"""
        self.assertEqual(i18n.choose_language('de', 'es', [('de', 1)]), 'en')
        self.assertEqual(i18n.choose_language('de', None, [('fr', 1)]), 'fr')


class TestLanguage(HandlerTestCase):
    """The pages in English and in French"""

    def test_default_is_english(self):
        """no choice and no browser preference gives English"""
        html = self.client.get('/home').get_data(as_text=True)
        self.assertIn('<html lang="en">', html)
        self.assertIn('Deposit Funds', html)
        self.assertIn('Transaction History', html)
        self.assertNotIn('Déposer des fonds', html)

    def test_french_home_page(self):
        """?lang=fr translates the home page"""
        html = self.client.get('/home?lang=fr').get_data(as_text=True)
        self.assertIn('<html lang="fr">', html)
        self.assertIn('Déposer des fonds', html)
        self.assertIn('Envoyer un paiement', html)
        self.assertIn('Historique des transactions', html)
        self.assertIn('Solde actuel', html)
        self.assertIn('Se déconnecter', html)
        self.assertNotIn('Deposit Funds', html)
        self.assertNotIn('Current Balance', html)

    def test_french_login_and_signup_pages(self):
        """the signed out pages are translated too"""
        self.client.delete_cookie('token')
        login = self.client.get('/login?lang=fr').get_data(as_text=True)
        self.assertIn('Nom d&#39;utilisateur', login)
        self.assertIn('Créer un compte', login)
        self.assertIn('SE CONNECTER', login)
        signup = self.client.get('/signup?lang=fr').get_data(as_text=True)
        self.assertIn('Créer un nouveau compte', signup)
        self.assertIn('Prénom', signup)

    def test_footer_is_translated(self):
        """the demo disclaimer follows the language"""
        html = self.client.get('/home?lang=fr').get_data(as_text=True)
        self.assertIn('hébergé à des fins de démonstration', html)
        self.assertNotIn('This website is hosted for demo purposes only', html)

    def test_choice_is_remembered_in_a_cookie(self):
        """the next page without ?lang= keeps the language"""
        resp = self.client.get('/home?lang=fr')
        self.assertIn('lang=fr', resp.headers['Set-Cookie'])
        html = self.client.get('/home').get_data(as_text=True)
        self.assertIn('Déposer des fonds', html)
        self.client.get('/home?lang=en')
        html = self.client.get('/home').get_data(as_text=True)
        self.assertIn('Deposit Funds', html)

    def test_unsupported_language_is_ignored(self):
        """an unknown ?lang= gives English and sets no cookie"""
        resp = self.client.get('/home?lang=xx')
        self.assertIn('Deposit Funds', resp.get_data(as_text=True))
        self.assertNotIn('lang=', resp.headers.get('Set-Cookie', ''))

    def test_browser_language(self):
        """a French browser gets French without a choice"""
        resp = self.client.get('/home',
                               headers={'Accept-Language': 'fr-FR,fr;q=0.9'})
        self.assertIn('Déposer des fonds', resp.get_data(as_text=True))
        self.assertNotIn('Set-Cookie', resp.headers)

    def test_language_switcher(self):
        """both languages are offered and the current one is marked"""
        html = self.client.get('/home?lang=fr').get_data(as_text=True)
        self.assertIn('id="lang-en"', html)
        self.assertIn('id="lang-fr"', html)
        self.assertIn('href="/home?lang=en"', html)
        self.assertIn('Français', html)

    def test_switcher_keeps_other_query_parameters(self):
        """switching language does not drop the message being shown"""
        html = self.client.get('/home?msg=Payment+successful&lang=fr') \
            .get_data(as_text=True)
        self.assertIn('href="/home?msg=Payment+successful&amp;lang=en"', html)

    def test_handler_messages_are_translated(self):
        """the banner after a payment follows the language"""
        english = self.client.get('/home?msg=Payment+successful') \
            .get_data(as_text=True)
        self.assertIn('Payment successful', english)
        french = self.client.get('/home?msg=Payment+successful&lang=fr') \
            .get_data(as_text=True)
        self.assertIn('Paiement effectué', french)

    def test_unknown_message_is_shown_as_is(self):
        """a message without a translation is not lost"""
        html = self.client.get('/home?msg=Hello&lang=fr').get_data(as_text=True)
        self.assertIn('Hello', html)

    def test_failed_payment_in_french(self):
        """the failure banner and its reason are translated"""
        resp = self.client.post('/payment?lang=fr', data={
            'account_num': '9999999999', 'amount': 'abc', 'uuid': 'u1'})
        self.assertEqual(resp.status_code, 400)
        text = resp.get_data(as_text=True)
        self.assertIn('Échec du paiement : abc n&#39;est pas un nombre valide',
                      text)

    def test_failed_payment_in_english(self):
        """English failure messages are unchanged"""
        text = self.payment(amount='abc').get_data(as_text=True)
        self.assertIn('Payment failed: abc is not a valid number', text)

    def test_month_follows_the_language(self):
        """transaction dates use the month names of the language"""
        stamp = '2026-02-03T10:00:00.000000+0000'
        format_month = self.app.jinja_env.globals['format_timestamp_month']
        with self.app.test_request_context('/home?lang=fr'):
            self.app.preprocess_request()
            self.assertEqual(format_month(stamp), 'févr.')
        with self.app.test_request_context('/home'):
            self.app.preprocess_request()
            self.assertEqual(format_month(stamp), 'Feb')
