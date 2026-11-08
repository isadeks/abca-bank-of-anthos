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
Tests for the large payment confirmation step in the Send Payment modal
"""

import os
import re
import unittest
from unittest.mock import patch, mock_open

from flask import render_template
from requests.exceptions import RequestException

import frontend

ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
}

SCRIPT = os.path.join(os.path.dirname(frontend.__file__), 'static', 'scripts', 'index.js')


def render_home():
    """Render the home page template with no backend data"""
    with patch('frontend.open', mock_open(read_data='foo')), \
            patch('os.environ', ENV), \
            patch('frontend.requests.get', side_effect=RequestException):
        app = frontend.create_app()
    with app.test_request_context('/home'):
        return render_template('index.html',
                               account_id='1234567890', balance=500000,
                               bank_name='Bank of Anthos', cluster_name='c',
                               contacts=[], cymbal_logo='false', history=[],
                               message=None, name='Test', platform=None,
                               platform_display_name=None, pod_name='p',
                               pod_zone='z')


class TestPaymentConfirmationMarkup(unittest.TestCase):
    """The Send Payment modal contains a confirmation step"""

    @classmethod
    def setUpClass(cls):
        cls.html = render_home()

    def test_confirmation_step_is_hidden_and_has_threshold(self):
        """the confirmation step starts hidden and the threshold is $1,000"""
        match = re.search(r'<div[^>]*id="payment-confirm"[^>]*>', self.html)
        self.assertIsNotNone(match)
        self.assertIn('hidden', match.group(0))
        self.assertIn('data-threshold="1000"', match.group(0))

    def test_confirmation_step_has_back_and_confirm_buttons(self):
        """the user can go back or confirm the payment"""
        self.assertIn('id="payment-confirm-message"', self.html)
        self.assertIn('id="payment-confirm-back"', self.html)
        self.assertIn('id="payment-confirm-send"', self.html)

    def test_confirmation_step_is_inside_the_payment_form(self):
        """confirming submits the payment form"""
        form = self.html[self.html.index('id="payment-form"'):]
        form = form[:form.index('</form>')]
        self.assertIn('id="payment-confirm"', form)

    def test_script_asks_for_confirmation_above_threshold(self):
        """the submit handler shows the message before submitting large payments"""
        with open(SCRIPT, encoding='utf-8') as script:
            source = script.read()
        self.assertIn('amount > largePaymentThreshold', source)
        self.assertIn('You are about to send $', source)
