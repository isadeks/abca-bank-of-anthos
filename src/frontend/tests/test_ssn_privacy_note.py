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

"""The sign-up page explains why the SSN is collected."""

import os
import unittest

TEMPLATE = os.path.join(os.path.dirname(__file__), '..', 'templates',
                        'signup.html')


class TestSsnPrivacyNote(unittest.TestCase):
    """The SSN field has a muted help line under it"""

    def setUp(self):
        with open(TEMPLATE, encoding='utf-8') as f:
            self.html = f.read()

    def test_note_is_muted_and_has_text(self):
        """the help line has the expected text and muted styling"""
        self.assertRegex(
            self.html,
            r'<small id="ssn-help" class="[^"]*text-muted[^"]*">'
            r'We only use your SSN to verify your identity\.</small>')

    def test_note_follows_ssn_input(self):
        """the note comes right after the SSN input"""
        self.assertGreater(self.html.index('id="ssn-help"'),
                           self.html.index('id="ssn" name="ssn"'))
        self.assertLess(self.html.index('id="ssn-help"'),
                        self.html.index('id="signup-birthday"'))
