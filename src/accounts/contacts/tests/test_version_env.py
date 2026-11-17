"""Tests for the contacts /version endpoint reading the VERSION env var."""

import unittest
from unittest.mock import patch, mock_open

from contacts.contacts import create_app


class TestVersionEnv(unittest.TestCase):
    """Version endpoint tests"""

    def _client(self, extra_env, remove=()):
        env = {
            "VERSION": "unused",
            "PUB_KEY_PATH": "/tmp/key",
            "LOCAL_ROUTING_NUM": "123456789",
            "ACCOUNTS_DB_URI": "sqlite://",
            "ENABLE_TRACING": "false",
        }
        env.update(extra_env)
        with patch("builtins.open", mock_open(read_data="1")):
            with patch.dict("os.environ", env):
                for key in remove:
                    del_key = key
                    import os
                    os.environ.pop(del_key, None)
                with patch("contacts.contacts.ContactsDb"):
                    return create_app().test_client()

    def test_version_from_env(self):
        """VERSION env var is returned as plain text"""
        response = self._client({"VERSION": "v1.2.3"}).get("/version")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"v1.2.3")
        self.assertTrue(response.content_type.startswith("text/plain"))

    def test_version_unknown_when_unset(self):
        """'unknown' is returned when VERSION is not set"""
        response = self._client({}, remove=("VERSION",)).get("/version")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"unknown")
