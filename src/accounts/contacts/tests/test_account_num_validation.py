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
Tests for account number validation when adding contacts
"""

import json
import unittest
from unittest.mock import patch, mock_open

from contacts.contacts import create_app
from contacts.tests.constants import (
    EXAMPLE_CONTACT,
    EXAMPLE_USER,
    EXAMPLE_PUBLIC_KEY,
    EXAMPLE_HEADERS,
    )

INVALID_ACCT_MESSAGE = b"invalid account number"


class TestAccountNumValidation(unittest.TestCase):
    """Malformed account numbers are rejected with a clear message"""

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
                    self.mocked_db = mock_db
                    self.flask_app = create_app()
                    self.flask_app.config["TESTING"] = True
                    self.test_app = self.flask_app.test_client()
                    self.flask_app.config["PUBLIC_KEY"] = EXAMPLE_PUBLIC_KEY
                    self.mocked_db.return_value.get_contacts.return_value = []

    def post_account_num(self, account_num):
        """Post a new contact with the given account number"""
        contact = EXAMPLE_CONTACT.copy()
        contact["account_num"] = account_num
        return self.test_app.post(
            "/contacts/{}".format(EXAMPLE_USER),
            headers=EXAMPLE_HEADERS,
            data=json.dumps(contact),
        )

    def assert_rejected(self, account_num):
        """Assert the account number gets a 4xx with the error message"""
        response = self.post_account_num(account_num)
        self.assertGreaterEqual(response.status_code, 400)
        self.assertLess(response.status_code, 500)
        self.assertEqual(response.data, INVALID_ACCT_MESSAGE)
        self.mocked_db.return_value.add_contact.assert_not_called()

    def test_nine_digit_account_num_rejected(self):
        """Done means 1: 9 digits is rejected with an error"""
        self.assert_rejected("123123123")

    def test_eleven_digit_account_num_rejected(self):
        """Done means 2: 11 digits is rejected with an error"""
        self.assert_rejected("12312312312")

    def test_account_num_with_letters_rejected(self):
        """Done means 3: letters are rejected with an error"""
        self.assert_rejected("12345abcde")

    def test_valid_ten_digit_account_num_accepted(self):
        """Done means 4: a valid 10 digit number gives 201"""
        response = self.post_account_num("1234567890")
        self.assertEqual(response.status_code, 201)
        self.mocked_db.return_value.add_contact.assert_called_once()
