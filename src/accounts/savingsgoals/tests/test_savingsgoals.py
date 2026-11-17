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

"""Unit tests for the savings goals service"""

import unittest
from unittest.mock import MagicMock, patch, mock_open

import jwt
import requests

from savingsgoals.savingsgoals import create_app
from savingsgoals.tests.constants import (
    EXAMPLE_ACCT, EXAMPLE_PUBLIC_KEY, EXAMPLE_USER, auth_headers, make_token)

GOAL = {"id": 1, "name": "Trip", "target": 50000, "saved": 0,
        "account_num": "7123456789"}


def backend(status, body=None, text=""):
    """A fake backend response"""
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.json.return_value = body
    if status >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(text)
    return resp


class GoalsTestCase(unittest.TestCase):
    """Builds the app with the database and backends mocked"""

    def setUp(self):
        env = {"VERSION": "1", "LOCAL_ROUTING_NUM": "883745000",
               "PUB_KEY_PATH": "k", "ENABLE_TRACING": "false",
               "TRANSACTIONS_API_ADDR": "ledgerwriter:8080",
               "BALANCES_API_ADDR": "balancereader:8080"}
        with patch("savingsgoals.savingsgoals.open", mock_open(read_data="x")), \
                patch("os.environ", env), \
                patch("savingsgoals.savingsgoals.GoalsDb") as mock_db:
            self.db = mock_db.return_value
            self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["PUBLIC_KEY"] = EXAMPLE_PUBLIC_KEY
        self.client = self.app.test_client()
        self.db.count_goals.return_value = 0
        self.db.get_goal.return_value = dict(GOAL)
        self.get = patch("savingsgoals.savingsgoals.requests.get",
                         return_value=backend(200, 10000)).start()
        self.post = patch("savingsgoals.savingsgoals.requests.post",
                          return_value=backend(201)).start()
        self.addCleanup(patch.stopall)

    def url(self, suffix=""):
        """Goals URL of the example user"""
        return f"/goals/{EXAMPLE_USER}{suffix}"


class TestListAndCreate(GoalsTestCase):
    """GET and POST /goals/<user>"""

    def test_list_goals(self):
        """the user's goals are returned"""
        self.db.get_goals.return_value = [GOAL]
        resp = self.client.get(self.url(), headers=auth_headers())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), [GOAL])

    def test_requires_valid_token_for_that_user(self):
        """no token, a bad token, or another user's token gives 401"""
        other = {"Authorization": "Bearer " + make_token("someoneelse")}
        for headers in ({}, {"Authorization": "Bearer nope"}, other):
            resp = self.client.get(self.url(), headers=headers)
            self.assertEqual(resp.status_code, 401)
            resp = self.client.post(self.url(), json={}, headers=headers)
            self.assertEqual(resp.status_code, 401)
        self.db.get_goals.assert_not_called()

    def test_create_goal(self):
        """a valid goal is created"""
        self.db.add_goal.return_value = GOAL
        resp = self.client.post(self.url(), json={"name": " Trip ", "target": 50000},
                                headers=auth_headers())
        self.assertEqual(resp.status_code, 201)
        self.db.add_goal.assert_called_once_with(EXAMPLE_USER, "Trip", 50000)

    def test_name_of_40_characters_is_accepted_41_is_not(self):
        """the name limit is 40 characters"""
        self.db.add_goal.return_value = GOAL
        ok = self.client.post(self.url(), json={"name": "a" * 40, "target": 100},
                              headers=auth_headers())
        self.assertEqual(ok.status_code, 201)
        bad = self.client.post(self.url(), json={"name": "a" * 41, "target": 100},
                               headers=auth_headers())
        self.assertEqual(bad.status_code, 400)
        self.assertIn(b"40 characters or fewer", bad.data)

    def test_invalid_goals_are_rejected(self):
        """missing, blank or non-positive values give 400"""
        bodies = [None, {}, {"name": "x"}, {"target": 5},
                  {"name": "  ", "target": 5}, {"name": 5, "target": 5},
                  {"name": "x", "target": 0}, {"name": "x", "target": -5},
                  {"name": "x", "target": "5"}, {"name": "x", "target": 1.5},
                  {"name": "x", "target": True}]
        for body in bodies:
            with self.subTest(body=body):
                resp = self.client.post(self.url(), json=body,
                                        headers=auth_headers())
                self.assertEqual(resp.status_code, 400)
        self.db.add_goal.assert_not_called()

    def test_goal_limit(self):
        """too many goals gives 400"""
        self.db.count_goals.return_value = 20
        resp = self.client.post(self.url(), json={"name": "x", "target": 5},
                                headers=auth_headers())
        self.assertEqual(resp.status_code, 400)


class TestDelete(GoalsTestCase):
    """DELETE /goals/<user>/<id>"""

    def test_delete(self):
        """an existing goal is deleted"""
        self.db.delete_goal.return_value = True
        resp = self.client.delete(self.url("/1"), headers=auth_headers())
        self.assertEqual(resp.status_code, 204)
        self.db.delete_goal.assert_called_once_with(EXAMPLE_USER, 1)

    def test_delete_missing(self):
        """an unknown goal gives 404"""
        self.db.delete_goal.return_value = False
        resp = self.client.delete(self.url("/9"), headers=auth_headers())
        self.assertEqual(resp.status_code, 404)


class TestContribute(GoalsTestCase):
    """POST /goals/<user>/<id>/contributions"""

    def contribute(self, amount=2500, uuid="u1", goal_id=1):
        """Move money into a goal"""
        return self.client.post(self.url(f"/{goal_id}/contributions"),
                                json={"amount": amount, "uuid": uuid},
                                headers=auth_headers())

    def test_moves_money_as_a_ledger_transfer(self):
        """the transfer goes from checking to the goal's account"""
        resp = self.contribute(2500)
        self.assertEqual(resp.status_code, 201)
        sent = self.post.call_args.kwargs["json"]
        self.assertEqual(sent, {
            "fromAccountNum": EXAMPLE_ACCT, "fromRoutingNum": "883745000",
            "toAccountNum": "7123456789", "toRoutingNum": "883745000",
            "amount": 2500, "uuid": "u1"})
        self.assertEqual(self.post.call_args.args[0],
                         "http://ledgerwriter:8080/transactions")
        self.db.add_saved.assert_called_once_with(EXAMPLE_USER, 1, 2500)

    def test_whole_balance_is_allowed(self):
        """an amount equal to the balance is accepted"""
        self.assertEqual(self.contribute(10000).status_code, 201)

    def test_more_than_balance_is_rejected(self):
        """an amount above the balance sends nothing"""
        resp = self.contribute(10001)
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"more than the checking balance", resp.data)
        self.post.assert_not_called()
        self.db.add_saved.assert_not_called()

    def test_non_positive_amounts_are_rejected(self):
        """zero, negative and non-integer amounts give 400"""
        for amount in (0, -1, "10", 1.5, None, True):
            with self.subTest(amount=amount):
                self.assertEqual(self.contribute(amount).status_code, 400)
        self.post.assert_not_called()

    def test_missing_fields(self):
        """a body without amount or uuid gives 400"""
        resp = self.client.post(self.url("/1/contributions"), json={"amount": 5},
                                headers=auth_headers())
        self.assertEqual(resp.status_code, 400)

    def test_unknown_goal(self):
        """a goal that is not the user's gives 404 and sends nothing"""
        self.db.get_goal.return_value = None
        self.assertEqual(self.contribute().status_code, 404)
        self.post.assert_not_called()

    def test_balance_unavailable(self):
        """a balance reader failure gives 502 and sends nothing"""
        self.get.side_effect = requests.exceptions.ConnectionError
        self.assertEqual(self.contribute().status_code, 502)
        self.post.assert_not_called()

    def test_ledger_rejection_does_not_change_saved(self):
        """if the ledger refuses, the goal is not credited"""
        self.post.return_value = backend(400, text="duplicate")
        resp = self.contribute()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, b"duplicate")
        self.db.add_saved.assert_not_called()

    def test_ledger_down(self):
        """a ledger failure gives 502 and the goal is not credited"""
        self.post.side_effect = requests.exceptions.ConnectionError
        self.assertEqual(self.contribute().status_code, 502)
        self.db.add_saved.assert_not_called()

    def test_token_is_forwarded(self):
        """the user's token is used for the balance and the transfer"""
        self.contribute()
        expected = auth_headers()["Authorization"]
        self.assertEqual(self.get.call_args.kwargs["headers"]["Authorization"],
                         expected)
        self.assertEqual(self.post.call_args.kwargs["headers"]["Authorization"],
                         expected)
        self.assertEqual(jwt.get_unverified_header(
            expected.split(" ")[1])["alg"], "RS256")
