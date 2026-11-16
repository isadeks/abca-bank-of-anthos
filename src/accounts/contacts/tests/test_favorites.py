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
Tests for favourite contacts
"""

import json
import unittest
from unittest.mock import patch, mock_open

from sqlalchemy.exc import SQLAlchemyError

from contacts.contacts import create_app
from contacts.db import ContactsDb
from contacts.tests.constants import (
    EXAMPLE_CONTACT_DB_OBJ,
    EXAMPLE_HEADERS,
    EXAMPLE_PUBLIC_KEY,
    EXAMPLE_USER,
)


class TestFavoriteDb(unittest.TestCase):
    """Favourite flag in the db module"""

    def setUp(self):
        self.db = ContactsDb("sqlite:///:memory:")
        self.db.contacts_table.create(self.db.engine)
        self.contact = EXAMPLE_CONTACT_DB_OBJ.copy()
        self.db.add_contact(self.contact)

    def test_new_contact_is_not_favorite(self):
        """the flag is off by default"""
        found = self.db.get_contacts("jdoe", include_favorite=True)
        self.assertFalse(found[0]["is_favorite"])

    def test_flag_is_left_out_by_default(self):
        """callers that don't ask for the flag get the old shape"""
        self.assertNotIn("is_favorite", self.db.get_contacts("jdoe")[0])

    def test_set_favorite_on_and_off(self):
        """the flag can be switched on and back off"""
        self.assertTrue(self.db.set_favorite("jdoe", "foo", True))
        self.assertTrue(self.db.get_contacts("jdoe", True)[0]["is_favorite"])
        self.assertTrue(self.db.set_favorite("jdoe", "foo", False))
        self.assertFalse(self.db.get_contacts("jdoe", True)[0]["is_favorite"])

    def test_set_favorite_unknown_contact(self):
        """nothing is updated for an unknown label or user"""
        self.assertFalse(self.db.set_favorite("jdoe", "nobody", True))
        self.assertFalse(self.db.set_favorite("other", "foo", True))

    def test_set_favorite_only_touches_one_contact(self):
        """other contacts keep their setting"""
        other = dict(self.contact, label="bar", account_num="1111111111")
        self.db.add_contact(other)
        self.db.set_favorite("jdoe", "foo", True)
        flags = {c["label"]: c["is_favorite"] for c in self.db.get_contacts("jdoe", True)}
        self.assertEqual({"foo": True, "bar": False}, flags)


class TestFavoriteEndpoint(unittest.TestCase):
    """Favourite endpoint of the contacts service"""

    def setUp(self):
        with patch("contacts.contacts.open", mock_open(read_data="foo")):
            with patch("os.environ", {"VERSION": "1", "LOCAL_ROUTING": "123456789",
                                      "PUBLIC_KEY": "1", "ENABLE_TRACING": "false"}):
                with patch("contacts.contacts.ContactsDb") as mock_db:
                    self.db = mock_db.return_value
                    self.flask_app = create_app()
                    self.flask_app.config["TESTING"] = True
                    self.client = self.flask_app.test_client()
                    self.flask_app.config["PUBLIC_KEY"] = EXAMPLE_PUBLIC_KEY
        self.url = "/contacts/" + EXAMPLE_USER + "/Mom/favorite"

    def put(self, body, url=None, headers=EXAMPLE_HEADERS):
        """PUT a JSON body"""
        return self.client.put(url or self.url, data=json.dumps(body), headers=headers)

    def test_switch_on(self):
        """200 and the new setting"""
        self.db.set_favorite.return_value = True
        response = self.put({"is_favorite": True})
        self.assertEqual(200, response.status_code)
        self.assertEqual({"label": "Mom", "is_favorite": True}, response.get_json())
        self.db.set_favorite.assert_called_once_with(EXAMPLE_USER, "Mom", True)

    def test_switch_off(self):
        """200 when switching off"""
        self.db.set_favorite.return_value = True
        response = self.put({"is_favorite": False})
        self.assertEqual(200, response.status_code)
        self.db.set_favorite.assert_called_once_with(EXAMPLE_USER, "Mom", False)

    def test_unknown_contact_404(self):
        """404 when there is no such contact"""
        self.db.set_favorite.return_value = False
        self.assertEqual(404, self.put({"is_favorite": True}).status_code)

    def test_invalid_body_400(self):
        """400 when the value is missing or not a boolean"""
        for body in ({}, {"is_favorite": "yes"}, {"is_favorite": 1}, []):
            self.assertEqual(400, self.put(body).status_code)
        self.db.set_favorite.assert_not_called()

    def test_wrong_user_401(self):
        """a user can't change another user's contacts"""
        response = self.put({"is_favorite": True}, url="/contacts/other/Mom/favorite")
        self.assertEqual(401, response.status_code)
        self.db.set_favorite.assert_not_called()

    def test_missing_token_401(self):
        """no token, no access"""
        response = self.put({"is_favorite": True}, headers={})
        self.assertEqual(401, response.status_code)

    def test_db_error_500(self):
        """500 on database failure"""
        self.db.set_favorite.side_effect = SQLAlchemyError()
        self.assertEqual(500, self.put({"is_favorite": True}).status_code)

    def test_list_asks_for_favorite_flag(self):
        """the list returns the flag of every contact"""
        contacts = [{"label": "a", "is_favorite": True}, {"label": "b", "is_favorite": False}]
        self.db.get_contacts.return_value = contacts
        response = self.client.get("/contacts/" + EXAMPLE_USER, headers=EXAMPLE_HEADERS)
        self.assertEqual(contacts, response.get_json())
        self.db.get_contacts.assert_called_once_with(EXAMPLE_USER, include_favorite=True)
