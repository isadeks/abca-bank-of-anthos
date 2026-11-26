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

"""The home page balance carries a tooltip."""

import os
import re
import unittest


class TestBalanceTooltip(unittest.TestCase):
    """The balance element has a title tooltip"""

    def test_balance_has_tooltip(self):
        """Done means 2: #current-balance has the tooltip text"""
        path = os.path.join(os.path.dirname(__file__), '..',
                            'templates', 'index.html')
        with open(path, encoding='utf-8') as f:
            html = f.read()
        tag = re.search(r'<span[^>]*id="current-balance"[^>]*>', html)
        self.assertIsNotNone(tag)
        self.assertIn('title="Your current available balance"', tag.group(0))
