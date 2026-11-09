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
Accessibility (WCAG 2.1 AA) tests for the login, payment and deposit forms.

The templates are rendered by the real app and parsed, so the markup that
assistive technology relies on (labels, dialog semantics, live regions) is
checked without a browser.
"""

import os
import unittest
from html.parser import HTMLParser
from unittest.mock import mock_open, patch
from requests.exceptions import RequestException

import frontend

ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
    'ENABLE_TRACING': 'false',
}

CONTACTS = [
    {'label': 'Alice', 'account_num': '1111111111', 'routing_num': '123456789',
     'is_external': False},
    {'label': 'Bank', 'account_num': '2222222222', 'routing_num': '987654321',
     'is_external': True},
]


class _Page(HTMLParser):
    """Collects the elements of a page by tag"""

    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.stack = []
        self.text = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        element = dict(attrs)
        element['_tag'] = tag
        self.elements.append(element)
        if tag not in ('input', 'meta', 'link', 'br', 'img', 'hr'):
            self.stack.append(element)

    def handle_endtag(self, tag):
        while self.stack:
            if self.stack.pop()['_tag'] == tag:
                break

    def handle_data(self, data):
        for element in self.stack:
            element['_text'] = element.get('_text', '') + data

    def by_id(self, element_id):
        """Return the element with the id, or None"""
        for element in self.elements:
            if element.get('id') == element_id:
                return element
        return None

    def ids(self):
        """All ids in the page, with repetitions"""
        return [e['id'] for e in self.elements if 'id' in e]

    def labelled_ids(self):
        """Ids of the controls that a <label for> points to"""
        return {e['for'] for e in self.elements if e['_tag'] == 'label' and 'for' in e}

    def inside(self, ancestor_id, tag):
        """Elements of the given tag that are in the subtree of ancestor_id"""
        result, depth_marker = [], None
        # elements are in document order; use the raw html for subtree boundaries
        for element in self.elements:
            if element.get('id') == ancestor_id:
                depth_marker = True
            elif depth_marker and element['_tag'] == tag:
                result.append(element)
        return result


class TestFormAccessibility(unittest.TestCase):
    """Rendered markup of the login page and the home page's modal forms"""

    @classmethod
    def setUpClass(cls):
        with patch('frontend.open', mock_open(read_data='foo')), \
                patch('os.environ', dict(ENV)), \
                patch('frontend.requests.get', side_effect=RequestException):
            cls.app = frontend.create_app()
            cls.app.config['TESTING'] = True
            with cls.app.test_request_context('/'):
                cls.home_html = frontend.render_template(
                    'index.html', account_id='1234567890', balance=10000,
                    bank_name='Bank of Anthos', cluster_name=None,
                    contacts=CONTACTS, cymbal_logo='false', history=[],
                    message='Payment failed: nope', name='Test', platform=None,
                    platform_display_name=None, pod_name=None, pod_zone=None)
            cls.login_html = cls.app.test_client().get('/login').get_data(as_text=True)
        cls.home = _Page(cls.home_html)
        cls.login = _Page(cls.login_html)

    def _assert_inputs_labelled(self, page, form_id):
        labelled = page.labelled_ids()
        for field in page.inside(form_id, 'input') + page.inside(form_id, 'select'):
            if field.get('type') == 'hidden':
                continue
            self.assertIn(field.get('id'), labelled,
                          'input %s has no <label for>' % field.get('id'))

    def test_login_inputs_have_labels_that_match_ids(self):
        """every visible login input is the target of a <label for>"""
        self._assert_inputs_labelled(self.login, 'login-form')
        labelled = self.login.labelled_ids()
        self.assertIn('login-username', labelled)
        self.assertIn('login-password', labelled)

    def test_login_inputs_declare_autocomplete_purpose(self):
        """WCAG 1.3.5: username and password say what they are for"""
        self.assertEqual(self.login.by_id('login-username')['autocomplete'], 'username')
        self.assertEqual(self.login.by_id('login-password')['autocomplete'],
                         'current-password')

    def test_login_error_is_in_a_live_region(self):
        """the 'Login failed.' banner is inside a role=alert region present at load"""
        region = self.login.by_id('login-alert-region')
        self.assertEqual(region['role'], 'alert')
        self.assertIn('Login failed.', region['_text'])
        self.assertIsNotNone(self.login.by_id('alertBanner'))

    def test_deposit_and_payment_inputs_have_labels(self):
        """including the optional account / routing / label fields with only placeholders"""
        self._assert_inputs_labelled(self.home, 'deposit-form')
        self._assert_inputs_labelled(self.home, 'payment-form')
        for field in ('external_account_num', 'external_routing_num', 'external_label',
                      'contact_account_num', 'contact_label'):
            self.assertIn(field, self.home.labelled_ids())

    def test_modals_are_labelled_dialogs(self):
        """each modal is a role=dialog, aria-modal, named by its visible heading"""
        for modal_id in ('depositFunds', 'sendPayment'):
            modal = self.home.by_id(modal_id)
            self.assertEqual(modal['role'], 'dialog')
            self.assertEqual(modal['aria-modal'], 'true')
            title = self.home.by_id(modal['aria-labelledby'])
            self.assertIsNotNone(title)
            self.assertTrue(title['_text'].strip())

    def test_modal_openers_are_keyboard_operable(self):
        """the Deposit / Send Payment cards are focusable buttons that open a dialog"""
        openers = [e for e in self.home.elements if e.get('data-toggle') == 'modal']
        self.assertEqual(len(openers), 2)
        for opener in openers:
            self.assertEqual(opener['role'], 'button')
            self.assertEqual(opener['tabindex'], '0')
            self.assertEqual(opener['aria-haspopup'], 'dialog')
            self.assertEqual(opener['data-keyboard'], 'true')

    def test_ids_are_unique(self):
        """duplicate ids break label / aria-labelledby references"""
        for page in (self.home, self.login):
            ids = page.ids()
            self.assertEqual(len(ids), len(set(ids)))

    def test_failure_message_is_announced(self):
        """a 'failed' flash message is a role=alert, a success one a polite status"""
        self.assertEqual(self.home.by_id('alert-message-div')['role'], 'alert')
        with patch('os.environ', dict(ENV)), self.app.test_request_context('/'):
            html = frontend.render_template(
                'index.html', account_id='1234567890', balance=1, bank_name='B',
                cluster_name=None, contacts=CONTACTS, cymbal_logo='false',
                history=[], message='Deposit successful', name='T', platform=None,
                platform_display_name=None, pod_name=None, pod_zone=None)
        self.assertEqual(_Page(html).by_id('alert-message-div')['role'], 'status')

    def test_icon_only_controls_are_named(self):
        """close buttons carry an accessible name and icon ligatures are hidden"""
        for element in self.home.elements:
            if element['_tag'] == 'button' and 'close' in element.get('class', '').split():
                self.assertTrue(element.get('aria-label'))
            if 'material-icons' in element.get('class', '').split():
                self.assertEqual(element.get('aria-hidden'), 'true',
                                 'icon %s is read aloud' % element.get('_text'))

    def test_scripts_are_loaded_in_order(self):
        """a11y helpers are loaded before the page scripts that use them"""
        for html, script in ((self.home_html, 'index.js'), (self.login_html, 'login.js')):
            self.assertLess(html.index('static/scripts/a11y.js'),
                            html.index('static/scripts/' + script))
        self.assertTrue(os.path.exists(os.path.join(
            os.path.dirname(frontend.__file__), 'static', 'scripts', 'a11y.js')))


if __name__ == '__main__':
    unittest.main()
