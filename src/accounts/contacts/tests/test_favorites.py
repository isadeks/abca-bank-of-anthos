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
Tests for the favourite setting of contacts
"""

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


class TestFavoritesDb(unittest.TestCase):
    """Favourite setting in the db module"""

    def setUp(self):
        self.db = ContactsDb("sqlite:///:memory:")
        self.db.contacts_table.create(self.db.engine)
        self.contact = dict(EXAMPLE_CONTACT_DB_OBJ, username="bar")

    def test_contact_is_not_favorite_by_default(self):
        """contacts added without the setting are not favourites"""
        self.db.add_contact(self.contact)
        self.assertIs(self.db.get_contacts("bar")[0]["is_favorite"], False)

    def test_set_favorite_on_and_off(self):
        """the setting can be switched on and off again"""
        self.db.add_contact(self.contact)
        label = self.contact["label"]
        self.assertTrue(self.db.set_favorite("bar", label, True))
        self.assertIs(self.db.get_contacts("bar")[0]["is_favorite"], True)
        self.assertTrue(self.db.set_favorite("bar", label, False))
        self.assertIs(self.db.get_contacts("bar")[0]["is_favorite"], False)

    def test_set_favorite_only_changes_that_contact(self):
        """other contacts and other users are untouched"""
        self.db.add_contact(self.contact)
        self.db.add_contact(dict(self.contact, label="other"))
        self.db.add_contact(dict(self.contact, username="baz"))
        self.db.set_favorite("bar", self.contact["label"], True)
        favs = {c["label"]: c["is_favorite"] for c in self.db.get_contacts("bar")}
        self.assertEqual(favs, {self.contact["label"]: True, "other": False})
        self.assertIs(self.db.get_contacts("baz")[0]["is_favorite"], False)

    def test_set_favorite_unknown_contact_returns_false(self):
        """an unknown contact is reported"""
        self.assertFalse(self.db.set_favorite("bar", "nobody", True))


class TestFavoritesEndpoint(unittest.TestCase):
    """PUT /contacts/<username>/favorite"""

    def setUp(self):
        with patch("contacts.contacts.open", mock_open(read_data="foo")):
            with patch("os.environ", {"VERSION": "1", "LOCAL_ROUTING": "123456789",
                                      "PUBLIC_KEY": "1", "ENABLE_TRACING": "false"}):
                with patch("contacts.contacts.ContactsDb") as mock_db:
                    self.mocked_db = mock_db
                    app = create_app()
                    app.config["TESTING"] = True
                    app.config["PUBLIC_KEY"] = EXAMPLE_PUBLIC_KEY
                    self.client = app.test_client()
        self.url = "/contacts/{}/favorite".format(EXAMPLE_USER)
        self.set_favorite = self.mocked_db.return_value.set_favorite

    def test_200_switches_on(self):
        """valid request updates the db"""
        self.set_favorite.return_value = True
        resp = self.client.put(self.url, json={"label": "Mom", "is_favorite": True},
                               headers=EXAMPLE_HEADERS)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {"label": "Mom", "is_favorite": True})
        self.set_favorite.assert_called_once_with(EXAMPLE_USER, "Mom", True)

    def test_200_switches_off(self):
        """the setting can be switched off"""
        self.set_favorite.return_value = True
        resp = self.client.put(self.url, json={"label": "Mom", "is_favorite": False},
                               headers=EXAMPLE_HEADERS)
        self.assertEqual(resp.status_code, 200)
        self.set_favorite.assert_called_once_with(EXAMPLE_USER, "Mom", False)

    def test_404_unknown_contact(self):
        """unknown label"""
        self.set_favorite.return_value = False
        resp = self.client.put(self.url, json={"label": "Nope", "is_favorite": True},
                               headers=EXAMPLE_HEADERS)
        self.assertEqual(resp.status_code, 404)

    def test_400_invalid_body(self):
        """missing or non-boolean fields are rejected"""
        for body in ({}, {"label": "Mom"}, {"is_favorite": True},
                     {"label": "Mom", "is_favorite": "yes"}, {"label": 5, "is_favorite": True}):
            resp = self.client.put(self.url, json=body, headers=EXAMPLE_HEADERS)
            self.assertEqual(resp.status_code, 400, body)
        self.set_favorite.assert_not_called()

    def test_401_invalid_auth(self):
        """no token, or someone else's contacts"""
        body = {"label": "Mom", "is_favorite": True}
        self.assertEqual(self.client.put(self.url, json=body).status_code, 401)
        other = self.client.put("/contacts/other/favorite", json=body,
                                headers=EXAMPLE_HEADERS)
        self.assertEqual(other.status_code, 401)
        self.set_favorite.assert_not_called()

    def test_500_db_failure(self):
        """db errors"""
        self.set_favorite.side_effect = SQLAlchemyError("boom")
        resp = self.client.put(self.url, json={"label": "Mom", "is_favorite": True},
                               headers=EXAMPLE_HEADERS)
        self.assertEqual(resp.status_code, 500)
