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
    EXAMPLE_HEADERS,
    EXAMPLE_PUBLIC_KEY,
    EXAMPLE_USER,
    EXAMPLE_CONTACT_DB_OBJ,
)

URL = "/contacts/{}/{}/favourite".format(EXAMPLE_USER, "Mom")


class TestFavouriteEndpoint(unittest.TestCase):
    """Tests for the favourite endpoint"""

    def setUp(self):
        with patch("contacts.contacts.open", mock_open(read_data="foo")):
            with patch(
                "os.environ",
                {
                    "VERSION": "1",
                    "LOCAL_ROUTING": "123456789",
                    "PUBLIC_KEY": "1",
                    "ENABLE_TRACING": "false",
                },
            ):
                with patch("contacts.contacts.ContactsDb") as mock_db:
                    self.db = mock_db.return_value
                    app = create_app()
                    app.config["TESTING"] = True
                    app.config["PUBLIC_KEY"] = EXAMPLE_PUBLIC_KEY
                    self.client = app.test_client()

    def put(self, body, url=URL, headers=None):
        """PUT a json body"""
        return self.client.put(
            url, headers=EXAMPLE_HEADERS if headers is None else headers, data=json.dumps(body))

    def test_switch_on(self):
        """favourite can be switched on"""
        self.db.set_favourite.return_value = True
        response = self.put({"is_favourite": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"label": "Mom", "is_favourite": True})
        self.db.set_favourite.assert_called_once_with(EXAMPLE_USER, "Mom", True)

    def test_switch_off(self):
        """favourite can be switched off"""
        self.db.set_favourite.return_value = True
        response = self.put({"is_favourite": False})
        self.assertEqual(response.status_code, 200)
        self.db.set_favourite.assert_called_once_with(EXAMPLE_USER, "Mom", False)

    def test_unknown_contact_is_404(self):
        """missing contact gives 404"""
        self.db.set_favourite.return_value = False
        self.assertEqual(self.put({"is_favourite": True}).status_code, 404)

    def test_invalid_body_is_400(self):
        """non-boolean values are rejected"""
        for body in ({}, {"is_favourite": "yes"}, {"is_favourite": 1}, [True]):
            self.assertEqual(self.put(body).status_code, 400)
        self.db.set_favourite.assert_not_called()

    def test_other_user_is_401(self):
        """a user cannot change another user's contacts"""
        url = "/contacts/someoneelse/Mom/favourite"
        self.assertEqual(self.put({"is_favourite": True}, url=url).status_code, 401)
        self.db.set_favourite.assert_not_called()

    def test_missing_token_is_401(self):
        """no token is rejected"""
        response = self.put({"is_favourite": True}, headers={})
        self.assertEqual(response.status_code, 401)

    def test_db_failure_is_500(self):
        """database errors give 500"""
        self.db.set_favourite.side_effect = SQLAlchemyError()
        self.assertEqual(self.put({"is_favourite": True}).status_code, 500)

    def test_list_asks_for_favourite_flag(self):
        """the list is fetched with the favourite setting"""
        self.db.get_contacts.return_value = [{"label": "Mom", "is_favourite": True}]
        response = self.client.get(
            "/contacts/" + EXAMPLE_USER, headers=EXAMPLE_HEADERS)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [{"label": "Mom", "is_favourite": True}])
        self.db.get_contacts.assert_called_once_with(
            EXAMPLE_USER, include_favourite=True)


class TestFavouriteDb(unittest.TestCase):
    """Tests for the favourite column"""

    def setUp(self):
        self.db = ContactsDb("sqlite:///:memory:")
        self.db.contacts_table.create(self.db.engine)
        self.contact = EXAMPLE_CONTACT_DB_OBJ.copy()
        self.db.add_contact(self.contact)

    def test_off_by_default(self):
        """new contacts are not favourites"""
        contacts = self.db.get_contacts("jdoe", include_favourite=True)
        self.assertFalse(contacts[0]["is_favourite"])

    def test_flag_hidden_unless_asked(self):
        """default listing is unchanged"""
        self.assertNotIn("is_favourite", self.db.get_contacts("jdoe")[0])

    def test_toggle(self):
        """flag can be switched on and off"""
        self.assertTrue(self.db.set_favourite("jdoe", "foo", True))
        self.assertTrue(self.db.get_contacts("jdoe", True)[0]["is_favourite"])
        self.assertTrue(self.db.set_favourite("jdoe", "foo", False))
        self.assertFalse(self.db.get_contacts("jdoe", True)[0]["is_favourite"])

    def test_unknown_contact(self):
        """unknown label or user changes nothing"""
        self.assertFalse(self.db.set_favourite("jdoe", "nope", True))
        self.assertFalse(self.db.set_favourite("other", "foo", True))
