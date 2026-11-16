# Copyright 2020 Google LLC
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

"""Checks that the accounts-db image defines and seeds the contacts favourite flag."""

import unittest
from pathlib import Path

INITDB = Path(__file__).resolve().parents[1] / 'initdb'


class TestContactsFavouriteSchema(unittest.TestCase):
    def test_column_is_off_by_default(self):
        schema = (INITDB / '0-accounts-schema.sql').read_text()
        self.assertIn('is_favourite BOOLEAN NOT NULL DEFAULT FALSE', schema)

    def test_existing_databases_get_the_column(self):
        schema = (INITDB / '0-accounts-schema.sql').read_text()
        self.assertIn('ADD COLUMN IF NOT EXISTS is_favourite', schema)

    def test_demo_data_has_favourites(self):
        script = (INITDB / '1-load-testdata.sh').read_text()
        self.assertIn('mark_favourite "testuser" "Alice"', script)
