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
Unit tests for foreign currency quotes: the fee calculation, the rate
source (mocked) with its cache, and the /foreign-currency page.
"""

import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

import jwt
import requests

import fx
from test_payment_deposit_handlers import HandlerTestCase, TOKEN_DATA


def rate_response(rate, currency='EUR'):
    """A fake Frankfurter response"""
    resp = MagicMock()
    resp.json.return_value = {'base': 'USD', 'rates': {currency: rate}}
    return resp


class TestCalculateQuote(unittest.TestCase):
    """The fee calculation"""

    def test_margin_and_delivery(self):
        """100 EUR at 0.80 EUR/USD = $125, 2% fee = $2.50, +$5 delivery"""
        quote = fx.calculate_quote('100', '0.8', '2', '5')
        self.assertEqual(quote['subtotal'], Decimal('125.00'))
        self.assertEqual(quote['fee'], Decimal('2.50'))
        self.assertEqual(quote['delivery'], Decimal('5.00'))
        self.assertEqual(quote['total'], Decimal('132.50'))
        self.assertEqual(quote['customer_rate'], Decimal('0.784'))

    def test_rounds_to_cents(self):
        """amounts are rounded to cents"""
        quote = fx.calculate_quote('10', '3', '2.5', '0')
        self.assertEqual(quote['subtotal'], Decimal('3.33'))
        self.assertEqual(quote['fee'], Decimal('0.08'))
        self.assertEqual(quote['total'], Decimal('3.41'))

    def test_rejects_non_positive(self):
        """zero amounts and rates are errors"""
        with self.assertRaises(ValueError):
            fx.calculate_quote('0', '1', '2', '5')
        with self.assertRaises(ValueError):
            fx.calculate_quote('1', '0', '2', '5')


class TestFetchRate(unittest.TestCase):
    """The rate source, mocked"""

    @patch('fx.requests.get')
    def test_fetch(self, get):
        """asks Frankfurter for USD -> currency"""
        get.return_value = rate_response(0.92)
        rate = fx.fetch_rate('https://rates.test/v1/', 'EUR')
        self.assertEqual(rate, Decimal('0.92'))
        self.assertEqual(get.call_args[0][0], 'https://rates.test/v1/latest')
        self.assertEqual(get.call_args[1]['params'],
                         {'base': 'USD', 'symbols': 'EUR'})

    @patch('fx.requests.get')
    def test_cache_hit_and_expiry(self, get):
        """cached within the ttl, refetched after it, never stale"""
        now = [0]
        cache = fx.RateCache(ttl=60, clock=lambda: now[0])
        get.return_value = rate_response(0.9)
        fx.fetch_rate('u', 'EUR', cache)
        now[0] = 59
        fx.fetch_rate('u', 'EUR', cache)
        self.assertEqual(get.call_count, 1)
        now[0] = 61
        get.return_value = rate_response(0.95)
        self.assertEqual(fx.fetch_rate('u', 'EUR', cache), Decimal('0.95'))
        self.assertEqual(get.call_count, 2)

    @patch('fx.requests.get')
    def test_failure_does_not_use_stale_rate(self, get):
        """after expiry, a failing source raises rather than reusing"""
        now = [0]
        cache = fx.RateCache(ttl=60, clock=lambda: now[0])
        get.return_value = rate_response(0.9)
        fx.fetch_rate('u', 'EUR', cache)
        now[0] = 100
        get.side_effect = requests.exceptions.ConnectionError('down')
        with self.assertRaises(fx.RateUnavailable):
            fx.fetch_rate('u', 'EUR', cache)

    @patch('fx.requests.get')
    def test_bad_responses(self, get):
        """malformed or non-positive rates are unavailable"""
        for bad in ({'rates': {}}, {'rates': {'EUR': 0}}, {}):
            resp = MagicMock()
            resp.json.return_value = bad
            get.return_value = resp
            with self.assertRaises(fx.RateUnavailable):
                fx.fetch_rate('u', 'EUR')


class TestForeignCurrencyPage(HandlerTestCase):
    """The /foreign-currency route"""

    def get_page(self, query):
        """GETs the page, signed in"""
        return self.client.get('/foreign-currency', query_string=query)

    def setUp(self):
        super().setUp()
        self.fx_get = patch('fx.requests.get').start()
        self.addCleanup(patch.stopall)

    def test_requires_login(self):
        """no valid token redirects to login"""
        with patch('frontend.jwt.decode',
                   side_effect=jwt.InvalidTokenError):
            resp = self.get_page({})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers['Location'])

    def test_form_without_query(self):
        """the empty form renders without a quote"""
        html = self.get_page({}).get_data(as_text=True)
        self.assertIn('id="fx-form"', html)
        self.assertNotIn('id="fx-quote"', html)
        self.fx_get.assert_not_called()

    def test_quote(self):
        """a quote shows rate, fee, delivery and total in dollars"""
        self.fx_get.return_value = rate_response(0.8)
        resp = self.get_page({'currency': 'EUR', 'amount': '100'})
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('1 USD = 0.7800 EUR', html)   # 0.8 less 2.5% margin
        self.assertIn('$125.00', html)
        self.assertIn('$3.13', html)
        self.assertIn('$5.00', html)
        self.assertIn('$133.13', html)

    def test_rate_source_down(self):
        """an unreachable source gives a clear message and no quote"""
        self.fx_get.side_effect = requests.exceptions.ConnectionError('x')
        resp = self.get_page({'currency': 'EUR', 'amount': '100'})
        html = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 503)
        self.assertIn('Exchange rates are unavailable', html)
        self.assertNotIn('id="fx-quote"', html)

    def test_invalid_input(self):
        """bad currency or amounts are rejected without calling the source"""
        for query in ({'currency': 'XXX', 'amount': '5'},
                      {'currency': 'EUR', 'amount': '-5'},
                      {'currency': 'EUR', 'amount': 'abc'},
                      {'currency': 'EUR', 'amount': '1.234'},
                      {'currency': 'EUR', 'amount': 'NaN'},
                      {'currency': 'EUR', 'amount': ''}):
            resp = self.get_page(query)
            self.assertEqual(resp.status_code, 400, query)
            self.assertIn('id="fx-error"', resp.get_data(as_text=True))
        self.fx_get.assert_not_called()
