"""Tests for the empty-username sign-up message"""

import unittest
from unittest.mock import patch, mock_open

from userservice.userservice import create_app
from userservice.tests.constants import EXAMPLE_USER_REQUEST


class TestEmptyUsernameMessage(unittest.TestCase):
    """Empty username gets a friendly 400 message"""

    def setUp(self):
        with patch('userservice.userservice.open', mock_open(read_data='foo')):
            with patch(
                'os.environ',
                {
                    'VERSION': '1',
                    'TOKEN_EXPIRY_SECONDS': '3600',
                    'PRIV_KEY_PATH': '1',
                    'PUB_KEY_PATH': '1',
                    'ENABLE_TRACING': 'false',
                },
            ):
                with patch('userservice.userservice.UserDb'):
                    app = create_app()
                    app.config['TESTING'] = True
                    self.test_app = app.test_client()

    def test_empty_username(self):
        """empty username -> 400 and the new message"""
        req = EXAMPLE_USER_REQUEST.copy()
        req['username'] = ''
        response = self.test_app.post('/users', data=req)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, b'Please choose a username.')

    def test_other_empty_field_keeps_old_message(self):
        """other empty fields keep the old message"""
        req = EXAMPLE_USER_REQUEST.copy()
        req['firstname'] = ''
        response = self.test_app.post('/users', data=req)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, b'missing value for input field(s)')
