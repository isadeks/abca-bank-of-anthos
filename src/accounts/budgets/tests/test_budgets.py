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
Tests for budgets
"""

import json
import random
import unittest
from unittest.mock import patch, mock_open

from sqlalchemy.exc import SQLAlchemyError

from budgets.budgets import create_app
from budgets.tests.constants import (
    EXAMPLE_USER,
    EXAMPLE_PUBLIC_KEY,
    EXAMPLE_HEADERS,
    FORGED_TOKEN,
    INVALID_LIMITS,
    OTHER_USER_TOKEN,
)

URL = "/budget/{}".format(EXAMPLE_USER)


class TestBudgets(unittest.TestCase):
    """
    Tests cases for budgets
    """

    def setUp(self):
        """Setup Flask TestClient and mock budgets_db"""
        # mock opening files
        with patch("budgets.budgets.open", mock_open(read_data="foo")):
            # mock env vars
            with patch(
                "os.environ",
                {"VERSION": "1", "PUBLIC_KEY": "1", "ENABLE_TRACING": "false"},
            ):
                # mock db module as MagicMock, context manager handles cleanup
                with patch("budgets.budgets.BudgetsDb") as mock_db:
                    self.mocked_db = mock_db
                    self.flask_app = create_app()
                    self.flask_app.config["TESTING"] = True
                    self.test_app = self.flask_app.test_client()
                    # set public key
                    self.flask_app.config["PUBLIC_KEY"] = EXAMPLE_PUBLIC_KEY
                    self.db = self.mocked_db.return_value

    def test_version_endpoint_returns_200_status_code_correct_version(self):
        """test if correct version is returned"""
        version = str(random.randint(1, 9))
        self.flask_app.config["VERSION"] = version
        response = self.test_app.get("/version")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, version.encode())

    def test_ready_endpoint_200_status_code_ok_string(self):
        """test if correct response is returned from readiness probe"""
        response = self.test_app.get("/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"ok")

    def test_startup_creates_the_table(self):
        """the service creates its table when it starts"""
        self.db.create_table.assert_called_once_with()

    def test_get_budget_200_returns_limit(self):
        """test reading an existing budget"""
        self.db.get_budget.return_value = 25000
        response = self.test_app.get(URL, headers=EXAMPLE_HEADERS)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"limit_cents": 25000})
        self.db.get_budget.assert_called_once_with(EXAMPLE_USER)

    def test_get_budget_200_null_limit_when_none_is_set(self):
        """test reading the budget of a user that has none"""
        self.db.get_budget.return_value = None
        response = self.test_app.get(URL, headers=EXAMPLE_HEADERS)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"limit_cents": None})

    def test_set_budget_200_stores_limit(self):
        """test creating or updating a budget"""
        response = self.test_app.put(
            URL, headers=EXAMPLE_HEADERS, data=json.dumps({"limit_cents": 50000})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"limit_cents": 50000})
        self.db.set_budget.assert_called_once_with(EXAMPLE_USER, 50000)

    def test_set_budget_400_invalid_limits(self):
        """test that invalid limits are rejected and nothing is stored"""
        for limit in INVALID_LIMITS:
            with self.subTest(limit=limit):
                response = self.test_app.put(
                    URL, headers=EXAMPLE_HEADERS, data=json.dumps({"limit_cents": limit})
                )
                self.assertEqual(response.status_code, 400)
        self.db.set_budget.assert_not_called()

    def test_set_budget_400_missing_field_or_body(self):
        """test that a missing field, a non-object and an invalid body are rejected"""
        for body in ('{}', '{"limit": 5000}', '[5000]', 'not json'):
            with self.subTest(body=body):
                response = self.test_app.put(URL, headers=EXAMPLE_HEADERS, data=body)
                self.assertEqual(response.status_code, 400)
        self.db.set_budget.assert_not_called()

    def test_clear_budget_204(self):
        """test clearing a budget"""
        response = self.test_app.delete(URL, headers=EXAMPLE_HEADERS)
        self.assertEqual(response.status_code, 204)
        self.db.clear_budget.assert_called_once_with(EXAMPLE_USER)

    def test_401_without_token(self):
        """test that every call needs a login token"""
        for method in (self.test_app.get, self.test_app.put, self.test_app.delete):
            with self.subTest(method=method):
                response = method(URL, data=json.dumps({"limit_cents": 100}))
                self.assertEqual(response.status_code, 401)
        self.db.get_budget.assert_not_called()
        self.db.set_budget.assert_not_called()
        self.db.clear_budget.assert_not_called()

    def test_401_with_token_signed_by_another_key(self):
        """test that a forged token is denied"""
        response = self.test_app.get(URL, headers={"Authorization": FORGED_TOKEN})
        self.assertEqual(response.status_code, 401)

    def test_401_with_bearer_prefix_of_invalid_token(self):
        """test that the Bearer prefix is accepted but a bad token is not"""
        response = self.test_app.get(URL, headers={"Authorization": "Bearer nope"})
        self.assertEqual(response.status_code, 401)

    def test_401_for_another_users_budget(self):
        """test that a user sees and changes only their own data"""
        headers = {"Authorization": "Bearer " + OTHER_USER_TOKEN}
        self.assertEqual(self.test_app.get(URL, headers=headers).status_code, 401)
        self.assertEqual(
            self.test_app.put(URL, headers=headers, json={"limit_cents": 100}).status_code, 401
        )
        self.assertEqual(self.test_app.delete(URL, headers=headers).status_code, 401)
        self.db.get_budget.assert_not_called()
        self.db.set_budget.assert_not_called()
        self.db.clear_budget.assert_not_called()

    def test_500_on_database_errors(self):
        """test that database failures are reported as 500"""
        self.db.get_budget.side_effect = SQLAlchemyError()
        self.db.set_budget.side_effect = SQLAlchemyError()
        self.db.clear_budget.side_effect = SQLAlchemyError()
        self.assertEqual(self.test_app.get(URL, headers=EXAMPLE_HEADERS).status_code, 500)
        self.assertEqual(
            self.test_app.put(URL, headers=EXAMPLE_HEADERS, json={"limit_cents": 100}).status_code,
            500,
        )
        self.assertEqual(self.test_app.delete(URL, headers=EXAMPLE_HEADERS).status_code, 500)
