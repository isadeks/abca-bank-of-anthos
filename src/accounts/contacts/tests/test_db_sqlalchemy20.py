# Copyright 2024 Google LLC
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
Regression tests: ContactsDb uses only the SQLAlchemy 2.0 API (no legacy warnings)
and persists writes without relying on implicit autocommit.
"""

import unittest
import warnings

from sqlalchemy import text
from sqlalchemy.exc import SADeprecationWarning

from contacts.db import ContactsDb
from contacts.tests.constants import EXAMPLE_CONTACT_DB_OBJ


class TestDbSqlAlchemy20(unittest.TestCase):
    """Test cases for SQLAlchemy 2.0 compatibility of ContactsDb"""

    def test_no_legacy_api_warnings(self):
        """ContactsDb construction and queries emit no SQLAlchemy 2.0 deprecation warnings"""
        with warnings.catch_warnings():
            warnings.simplefilter('error', SADeprecationWarning)
            db = ContactsDb('sqlite:///:memory:')
            db.contacts_table.create(db.engine)
            contact = EXAMPLE_CONTACT_DB_OBJ.copy()
            contact['username'] = 'warnfree'
            db.add_contact(contact)
            contact.pop('username')
            self.assertEqual([contact], db.get_contacts('warnfree'))

    def test_metadata_is_not_bound(self):
        """The table metadata is not bound to an engine"""
        db = ContactsDb('sqlite:///:memory:')
        self.assertIsNone(getattr(db.contacts_table.metadata, 'bind', None))

    def test_add_contact_is_committed(self):
        """A contact added through add_contact is visible from another connection"""
        db = ContactsDb('sqlite:///:memory:')
        db.contacts_table.create(db.engine)
        contact = EXAMPLE_CONTACT_DB_OBJ.copy()
        contact['username'] = 'committed'
        db.add_contact(contact)
        with db.engine.connect() as conn:
            count = conn.execute(text('SELECT COUNT(*) FROM contacts')).scalar()
        self.assertEqual(1, count)
