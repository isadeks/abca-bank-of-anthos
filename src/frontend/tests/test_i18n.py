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
Tests for the English / Spanish language switch: the cookie it sets, and the
translated login, home, payment and deposit pages.
"""

import unittest
from unittest.mock import MagicMock, patch, mock_open

import requests
from requests.exceptions import RequestException

import frontend
import i18n

ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
    'LOCAL_ROUTING_NUM': '883745000',
}
TOKEN_DATA = {'user': 'testuser', 'acct': '1234567890', 'name': 'Test'}


class TestTranslate(unittest.TestCase):
    """The translation helpers"""

    def test_spanish_translation(self):
        """known strings are translated"""
        self.assertEqual(i18n.translate('Sign in', 'es'), 'Iniciar sesión')

    def test_english_is_unchanged(self):
        """English and unknown languages return the original text"""
        self.assertEqual(i18n.translate('Sign in', 'en'), 'Sign in')
        self.assertEqual(i18n.translate('Sign in', 'fr'), 'Sign in')

    def test_unknown_text_is_unchanged(self):
        """strings without a translation (e.g. backend errors) pass through"""
        self.assertEqual(i18n.translate('some backend error', 'es'),
                         'some backend error')

    def test_normalize_lang(self):
        """only supported languages are accepted"""
        self.assertEqual(i18n.normalize_lang('es'), 'es')
        self.assertEqual(i18n.normalize_lang('xx'), 'en')
        self.assertEqual(i18n.normalize_lang(None), 'en')


class TestLanguageSwitch(unittest.TestCase):
    """The language switch and the translated pages"""

    def setUp(self):
        patches = [
            patch('os.environ', dict(ENV)),
            patch('frontend.open', mock_open(read_data='foo')),
            patch('frontend.requests.get', side_effect=RequestException),
            patch('frontend.jwt.decode', return_value=TOKEN_DATA),
            patch('frontend.ApiCall.make_call', return_value=None),
            patch('frontend.sleep'),
        ]
        for started in patches:
            started.start()
            self.addCleanup(started.stop)
        post_patch = patch('frontend.requests.post')
        self.post = post_patch.start()
        self.addCleanup(post_patch.stop)
        self.client = frontend.create_app().test_client()

    def sign_in(self):
        """Give the client a (mocked) valid token"""
        self.client.set_cookie('token', 'abc')

    def use_spanish(self):
        """Select Spanish like the header switch does"""
        self.client.set_cookie('lang', 'es')

    def test_login_is_english_by_default(self):
        """no cookie: English, and the switch is in the header"""
        html = self.client.get('/login').get_data(as_text=True)
        self.assertIn('>Sign in<', html)
        self.assertIn('id="lang-en"', html)
        self.assertIn('id="lang-es"', html)
        self.assertIn('<html lang="en">', html)

    def test_login_in_spanish(self):
        """the login page is translated"""
        self.use_spanish()
        html = self.client.get('/login').get_data(as_text=True)
        self.assertIn('INICIAR SESIÓN', html)
        self.assertIn('>Usuario</label>', html)
        self.assertIn('>Contraseña</label>', html)
        self.assertIn('Crear una cuenta', html)
        self.assertNotIn('>Sign in<', html)
        self.assertIn('<html lang="es">', html)

    def test_home_in_spanish(self):
        """the home page, deposit and payment forms are translated"""
        self.sign_in()
        self.use_spanish()
        html = self.client.get('/home').get_data(as_text=True)
        for text in ('Saldo actual', 'Depositar fondos', 'Enviar pago',
                     'Historial de transacciones', 'Hacer un depósito',
                     'Enviar un pago', 'Destinatario', 'Cuenta externa',
                     'Importe del depósito', 'Importe de la transacción',
                     'Cancelar', 'Cerrar sesión'):
            self.assertIn(text, html)
        self.assertNotIn('Current Balance', html)
        self.assertNotIn('Send a Payment', html)

    def test_home_in_english(self):
        """the home page stays English without the cookie"""
        self.sign_in()
        html = self.client.get('/home').get_data(as_text=True)
        self.assertIn('Current Balance', html)
        self.assertIn('Make a Deposit', html)
        self.assertNotIn('Saldo actual', html)

    def test_switch_sets_cookie_and_returns_to_page(self):
        """posting the switch stores the language and goes back"""
        resp = self.client.post('/language',
                                data={'lang': 'es', 'next': '/login'})
        self.assertEqual(resp.status_code, 303)
        self.assertTrue(resp.headers['Location'].endswith('/login'))
        self.assertIn('lang=es', resp.headers['Set-Cookie'])
        html = self.client.get('/login').get_data(as_text=True)
        self.assertIn('INICIAR SESIÓN', html)

    def test_switch_back_to_english(self):
        """the choice can be reverted"""
        self.use_spanish()
        resp = self.client.post('/language', data={'lang': 'en'})
        self.assertIn('lang=en', resp.headers['Set-Cookie'])

    def test_switch_ignores_unsupported_language(self):
        """an unknown language falls back to English"""
        resp = self.client.post('/language', data={'lang': 'zz'})
        self.assertIn('lang=en', resp.headers['Set-Cookie'])

    def test_switch_does_not_redirect_off_site(self):
        """only paths on this site are accepted as the next page"""
        for target in ('https://evil.example', '//evil.example', 'evil'):
            resp = self.client.post('/language',
                                    data={'lang': 'es', 'next': target})
            self.assertEqual(resp.status_code, 303)
            self.assertNotIn('evil', resp.headers['Location'])

    def test_success_message_in_spanish(self):
        """the redirect message after a payment is translated"""
        self.sign_in()
        self.use_spanish()
        html = self.client.get('/home?msg=Payment+successful') \
            .get_data(as_text=True)
        self.assertIn('Pago realizado con éxito', html)

    def test_failed_payment_in_spanish(self):
        """a failed payment reports the failure in Spanish"""
        self.sign_in()
        self.use_spanish()
        resp = self.client.post('/payment', data={
            'account_num': '9999999999', 'amount': 'abc', 'uuid': 'u1'})
        self.assertEqual(resp.status_code, 400)
        html = resp.get_data(as_text=True)
        self.assertIn('Error en el pago: abc no es un número válido', html)

    def test_failed_deposit_in_spanish(self):
        """a rejected deposit reports the failure and reason in Spanish"""
        self.sign_in()
        self.use_spanish()
        resp = self.client.post('/deposit', data={
            'account': 'add', 'external_account_num': '1111111111',
            'external_routing_num': '883745000', 'amount': '10',
            'uuid': 'u2'})
        self.assertEqual(resp.status_code, 400)
        html = resp.get_data(as_text=True)
        self.assertIn('Error en el depósito: número de ruta no válido', html)

    def test_failed_payment_in_english(self):
        """English messages are unchanged"""
        self.sign_in()
        self.post.return_value = MagicMock(status_code=500, text='boom')
        self.post.return_value.raise_for_status.side_effect = \
            requests.exceptions.HTTPError('boom')
        resp = self.client.post('/payment', data={
            'account_num': '9999999999', 'amount': '10', 'uuid': 'u1'})
        self.assertIn('Payment failed: boom', resp.get_data(as_text=True))
