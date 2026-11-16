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

"""Checks that the contacts table has the favourite flag, off by default, in every copy of the schema."""

import re
import unittest
from pathlib import Path

ACCOUNTS_DB = Path(__file__).resolve().parents[1]
SCHEMAS = [
    ACCOUNTS_DB / 'initdb' / '0-accounts-schema.sql',
    ACCOUNTS_DB / 'k8s' / 'components' / 'init-db-job' / 'init-db-job.yaml',
]
COLUMN = re.compile(r'is_favorite BOOLEAN NOT NULL DEFAULT FALSE', re.I)


class ContactsFavoriteSchemaTest(unittest.TestCase):
    def test_schema_has_favorite_column_off_by_default(self):
        for schema in SCHEMAS:
            text = schema.read_text()
            # in CREATE TABLE and in the ALTER for existing databases
            self.assertEqual(len(COLUMN.findall(text)), 2, schema)
            self.assertIn('ADD COLUMN IF NOT EXISTS is_favorite', text, schema)

    def test_demo_data_inserts_name_their_columns(self):
        for path in (ACCOUNTS_DB / 'initdb').glob('1-load-testdata.*'):
            text = path.read_text()
            self.assertNotIn('INSERT INTO contacts VALUES', text, path)
            self.assertIn('is_favorite', text, path)


if __name__ == '__main__':
    unittest.main()
