"""Tests for the /version endpoint fallback."""
import unittest
from unittest.mock import patch, mock_open

from contacts.contacts import create_app


class TestVersionUnknown(unittest.TestCase):
    def test_unknown_when_version_unset(self):
        env = {
            "VERSION": "1",
            "LOCAL_ROUTING": "123456789",
            "PUBLIC_KEY": "1",
            "ENABLE_TRACING": "false",
        }
        with patch("contacts.contacts.open", mock_open(read_data="foo")), \
                patch("os.environ", env), \
                patch("contacts.contacts.ContactsDb"):
            app = create_app()
        app.config["VERSION"] = None
        resp = app.test_client().get("/version")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b"contacts unknown")
