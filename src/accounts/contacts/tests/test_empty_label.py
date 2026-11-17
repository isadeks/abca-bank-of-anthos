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
Tests for empty contact labels
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

EMPTY_MESSAGE = b"invalid account label"


class TestEmptyLabel(unittest.TestCase):
    """Empty or whitespace-only labels are rejected with a clear message"""

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

    def post_label(self, label):
        """Post a new contact with the given label"""
        contact = EXAMPLE_CONTACT.copy()
        contact["label"] = label
        return self.test_app.post(
            "/contacts/{}".format(EXAMPLE_USER),
            headers=EXAMPLE_HEADERS,
            data=json.dumps(contact),
        )

    def test_empty_or_blank_label_is_rejected_with_clear_message(self):
        """empty and whitespace-only labels give 400; nothing is saved"""
        for label in ["", " ", "   ", "\t", "\n"]:
            with self.subTest(label=label):
                response = self.post_label(label)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data, EMPTY_MESSAGE)
        self.mocked_db.return_value.add_contact.assert_not_called()
