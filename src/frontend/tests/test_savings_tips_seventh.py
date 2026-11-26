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

"""Unit tests for the seventh tip on /savings-tips."""

import re

from test_payment_deposit_handlers import HandlerTestCase


class TestSavingsTipsSeventh(HandlerTestCase):
    """The savings tips page lists a seventh tip"""

    def setUp(self):
        super().setUp()
        self.client.delete_cookie('token')

    def test_seventh_tip(self):
        """Done means 1, Done means 2, Done means 3: seven tips, the last
        is the round-up tip; back link unchanged"""
        resp = self.client.get('/savings-tips')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        ul = html[html.index('id="savings-tips-list"'):html.index('</ul>')]
        tips = re.findall(r'<li>(.*?)</li>', ul)
        self.assertEqual(len(tips), 7)
        self.assertEqual(tips[6],
                         'Round up your card purchases into savings.')
        self.assertEqual(tips[5],
                         "Review your subscriptions every month and cancel "
                         "the ones you don't use.")
        self.assertIn('id="back-to-home"', html)
