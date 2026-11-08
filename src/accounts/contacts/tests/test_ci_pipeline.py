"""CI pipeline check: the contacts app starts and answers /ready."""
import unittest
from unittest.mock import mock_open, patch

from contacts.contacts import create_app


class TestReady(unittest.TestCase):
    def test_ready_endpoint(self):
        with patch("contacts.contacts.open", mock_open(read_data="foo")), \
             patch("os.environ", {"VERSION": "1", "LOCAL_ROUTING_NUM": "123456789", "ENABLE_TRACING": "false",
                                  "PUB_KEY_PATH": "1", "ACCOUNTS_DB_URI": "sqlite:///:memory:"}), \
             patch("contacts.contacts.ContactsDb"):
            app = create_app()
        app.config["TESTING"] = True
        self.assertEqual(app.test_client().get("/ready").status_code, 200)
