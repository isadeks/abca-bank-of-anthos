"""Tests for the userservice /version endpoint"""

import unittest
from unittest.mock import patch, mock_open

from userservice.userservice import create_app


def _client(version):
    env = {
        'TOKEN_EXPIRY_SECONDS': '100',
        'PRIV_KEY_PATH': '1',
        'PUB_KEY_PATH': '1',
        'ENABLE_TRACING': 'false',
    }
    if version is not None:
        env['VERSION'] = version
    with patch('userservice.userservice.open', mock_open(read_data='foo')):
        with patch('os.environ', env):
            with patch('userservice.userservice.UserDb'):
                app = create_app()
    app.config['TESTING'] = True
    return app.test_client()


class TestVersionEndpoint(unittest.TestCase):
    """Tests for GET /version"""

    def test_version_from_env(self):
        """VERSION env var is returned as plain text"""
        response = _client('v1.2.3').get('/version')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'v1.2.3')
        self.assertTrue(response.mimetype.startswith('text/plain'))

    def test_version_unknown_when_unset(self):
        """'unknown' is returned when VERSION is not set"""
        response = _client(None).get('/version')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'unknown')
