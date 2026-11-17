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
Foreign currency quotes: live rates from the Frankfurter API (ECB reference
rates) with a short cache, and the fee calculation.
"""

import time
from decimal import Decimal, ROUND_HALF_UP

import requests

SUPPORTED_CURRENCIES = {
    'EUR': 'Euro',
    'GBP': 'British pound',
    'JPY': 'Japanese yen',
    'CAD': 'Canadian dollar',
    'AUD': 'Australian dollar',
    'CHF': 'Swiss franc',
    'MXN': 'Mexican peso',
}
CENT = Decimal('0.01')


class RateUnavailable(Exception):
    """The rate source could not be reached or returned no usable rate."""


class RateCache:
    """Caches rates for ttl seconds; expired entries are never served."""

    def __init__(self, ttl=60, clock=time.monotonic):
        self.ttl = ttl
        self._clock = clock
        self._entries = {}

    def get(self, key):
        """The cached value, or None if missing or expired"""
        entry = self._entries.get(key)
        if entry is None:
            return None
        value, stored_at = entry
        if self._clock() - stored_at >= self.ttl:
            del self._entries[key]
            return None
        return value

    def put(self, key, value):
        """Stores a value"""
        self._entries[key] = (value, self._clock())


def fetch_rate(base_url, currency, cache=None, timeout=4):
    """
    Returns the units of `currency` per 1 USD as a Decimal.
    Raises RateUnavailable if the source can't be reached or answers badly.
    """
    if cache is not None:
        cached = cache.get(currency)
        if cached is not None:
            return cached
    try:
        resp = requests.get(base_url.rstrip('/') + '/latest',
                            params={'base': 'USD', 'symbols': currency},
                            timeout=timeout)
        resp.raise_for_status()
        rate = Decimal(str(resp.json()['rates'][currency]))
    except (requests.exceptions.RequestException, ValueError, KeyError,
            TypeError, ArithmeticError) as err:
        raise RateUnavailable(str(err)) from err
    if not rate.is_finite() or rate <= 0:
        raise RateUnavailable('invalid rate')
    if cache is not None:
        cache.put(currency, rate)
    return rate


def calculate_quote(amount, rate, margin_percent, delivery_charge):
    """
    Prices an order of `amount` units of foreign currency.

    rate: foreign units per 1 USD (market rate).
    The customer's rate is the market rate reduced by margin_percent; the
    fee is the difference that margin makes, in dollars. A flat
    delivery_charge (dollars) is added. Returns Decimals rounded to cents
    (the rates keep full precision).
    """
    amount = Decimal(amount)
    rate = Decimal(rate)
    margin = Decimal(margin_percent) / 100
    delivery = Decimal(delivery_charge)
    if amount <= 0 or rate <= 0:
        raise ValueError('amount and rate must be positive')
    subtotal = (amount / rate).quantize(CENT, ROUND_HALF_UP)
    fee = (amount / rate * margin).quantize(CENT, ROUND_HALF_UP)
    delivery = delivery.quantize(CENT, ROUND_HALF_UP)
    return {
        'market_rate': rate,
        'customer_rate': rate * (1 - margin),
        'subtotal': subtotal,
        'fee': fee,
        'delivery': delivery,
        'total': subtotal + fee + delivery,
    }
