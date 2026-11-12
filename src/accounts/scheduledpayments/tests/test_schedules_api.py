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
Tests for the create, list and cancel routes of the scheduled payments
service: validation, authentication and ownership.
"""

import datetime
import json
import unittest
from unittest.mock import patch

import requests

from scheduledpayments.tests import helpers
from scheduledpayments.tests.helpers import (
    ALICE, BOB, EXTERNAL, ACCOUNT, USER, auth, contacts_response)

TODAY = datetime.date(2026, 3, 31)


class ApiTestCase(unittest.TestCase):
    """The app on an in-memory database, with the contacts service mocked"""

    def setUp(self):
        self.app, self.db = helpers.build_app()
        self.client = self.app.test_client()
        patches = [
            patch("scheduledpayments.scheduledpayments.requests.get",
                  return_value=contacts_response([ALICE, BOB, EXTERNAL])),
            patch("scheduledpayments.scheduledpayments._today",
                  return_value=TODAY),
        ]
        self.get = patches[0].start()
        patches[1].start()
        self.addCleanup(patch.stopall)

    def create(self, headers=None, user=USER, **overrides):
        """POST a new schedule; defaults to a valid weekly payment to Alice"""
        body = {"account_num": ALICE["account_num"], "amount": 2500,
                "frequency": "weekly"}
        body.update(overrides)
        body = {k: v for k, v in body.items() if v is not None}
        return self.client.post(
            f"/schedules/{user}", headers=headers or auth(),
            data=json.dumps(body))

    def list(self, headers=None, user=USER):
        """GET the schedules of a user"""
        return self.client.get(f"/schedules/{user}", headers=headers or auth())


class TestCreate(ApiTestCase):
    """POST /schedules/<username>"""

    def test_creates_a_weekly_schedule(self):
        """201 with the schedule; the first payment is a week away"""
        resp = self.create()
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertEqual(data["account_num"], ALICE["account_num"])
        self.assertEqual(data["label"], "Alice")
        self.assertEqual(data["amount"], 2500)
        self.assertEqual(data["frequency"], "weekly")
        self.assertEqual(data["next_payment_date"], "2026-04-07")
        self.assertIsNone(data["last_status"])
        self.assertTrue(data["id"])

    def test_monthly_schedule_goes_by_the_month(self):
        """the 31st of March is followed by the end of April"""
        resp = self.create(frequency="monthly")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.get_json()["next_payment_date"], "2026-04-30")

    def test_schedule_is_stored_for_the_customer_and_their_account(self):
        """the owner and the paying account come from the token"""
        self.create()
        stored = self.db.list_schedules(USER)[0]
        self.assertEqual(stored["from_account_num"], ACCOUNT)
        self.assertEqual(stored["to_account_num"], ALICE["account_num"])
        self.assertEqual(stored["anchor_day"], 31)

    def test_contacts_are_read_with_the_customers_token(self):
        """the recipient is checked with the customer's own contacts"""
        headers = auth()
        self.create(headers=headers)
        call = self.get.call_args
        self.assertEqual(call.kwargs["url"], "http://contacts:8080/contacts/testuser")
        self.assertEqual(call.kwargs["headers"]["Authorization"],
                         headers["Authorization"])

    def test_invalid_amounts_are_rejected(self):
        """zero, negative, fractional, text, booleans and huge amounts give 400"""
        for amount in (0, -5, 10.5, "25", True, 50_000_001, [1], {"a": 1}):
            with self.subTest(amount=amount):
                resp = self.create(amount=amount)
                self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.db.list_schedules(USER), [])

    def test_largest_amount_is_accepted(self):
        """the limit is inclusive"""
        self.assertEqual(self.create(amount=50_000_000).status_code, 201)

    def test_invalid_frequencies_are_rejected(self):
        """only weekly and monthly are known"""
        for frequency in ("daily", "WEEKLY", "", "yearly", 7):
            with self.subTest(frequency=frequency):
                resp = self.create(frequency=frequency)
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.get_data(as_text=True),
                                 "frequency must be weekly or monthly")

    def test_missing_fields_are_rejected(self):
        """each field is required"""
        for field in ("account_num", "amount", "frequency"):
            with self.subTest(field=field):
                resp = self.create(**{field: None})
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.get_data(as_text=True),
                                 "missing required field(s)")

    def test_body_must_be_a_json_object(self):
        """garbage and lists give 400"""
        for data in ("not json", "[1, 2]", "null"):
            with self.subTest(data=data):
                resp = self.client.post(
                    f"/schedules/{USER}", headers=auth(), data=data)
                self.assertEqual(resp.status_code, 400)

    def test_recipient_must_be_one_of_the_customers_contacts(self):
        """an account that is not a contact is refused"""
        for account in ("1077441377", "1234", "abcdefghij", 1033623433):
            with self.subTest(account=account):
                resp = self.create(account_num=account)
                self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.db.list_schedules(USER), [])

    def test_external_accounts_are_not_valid_recipients(self):
        """an external contact can only deposit, so it can't be paid"""
        resp = self.create(account_num=EXTERNAL["account_num"])
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_data(as_text=True),
                         "the recipient is not one of your contacts")

    def test_contacts_service_failure_gives_502(self):
        """if the contacts can't be read, nothing is stored"""
        self.get.return_value = contacts_response([], status=500)
        self.assertEqual(self.create().status_code, 502)
        self.get.side_effect = requests.exceptions.ConnectionError
        self.assertEqual(self.create().status_code, 502)
        self.assertEqual(self.db.list_schedules(USER), [])


class TestList(ApiTestCase):
    """GET /schedules/<username>"""

    def test_empty_list(self):
        """a customer without schedules gets an empty list"""
        resp = self.list()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), [])

    def test_lists_the_customers_schedules_soonest_first(self):
        """weekly (7 days) comes before monthly (30 days)"""
        self.create(account_num=BOB["account_num"], frequency="monthly")
        self.create(account_num=ALICE["account_num"], frequency="weekly")
        data = self.list().get_json()
        self.assertEqual([d["label"] for d in data], ["Alice", "Bob"])
        self.assertEqual(
            sorted(data[0]), sorted(["id", "account_num", "label", "amount",
                                     "frequency", "next_payment_date",
                                     "last_status", "last_error",
                                     "last_attempt_date"]))

    def test_does_not_expose_internal_columns(self):
        """the paying account and username are not part of the answer"""
        self.create()
        body = self.list().get_data(as_text=True)
        self.assertNotIn(ACCOUNT, body)

    def test_shows_the_last_failure(self):
        """a failed payment is reported with its reason"""
        self.create()
        schedule = self.db.list_schedules(USER)[0]
        self.db.claim_attempt(
            schedule["schedule_id"], schedule["next_payment_date"],
            datetime.date(2026, 4, 14),
            datetime.datetime(2026, 4, 7, tzinfo=datetime.timezone.utc),
            datetime.timedelta(minutes=5), datetime.timedelta(minutes=50))
        self.db.finish_attempt(
            schedule["schedule_id"], schedule["next_payment_date"], False,
            "insufficient balance", datetime.date(2026, 4, 14),
            datetime.datetime(2026, 4, 7, tzinfo=datetime.timezone.utc))
        data = self.list().get_json()[0]
        self.assertEqual(data["last_status"], "failed")
        self.assertEqual(data["last_error"], "insufficient balance")
        self.assertEqual(data["last_attempt_date"], "2026-04-07")
        self.assertEqual(data["next_payment_date"], "2026-04-14")

    def test_a_customer_only_sees_their_own_schedules(self):
        """alice's schedules are not in testuser's list"""
        self.create()
        alice_headers = auth(user="alice", account=ALICE["account_num"])
        self.get.return_value = contacts_response(
            [{"label": "Testuser", "account_num": ACCOUNT,
              "routing_num": helpers.LOCAL_ROUTING, "is_external": False}])
        resp = self.create(headers=alice_headers, user="alice",
                           account_num=ACCOUNT)
        self.assertEqual(resp.status_code, 201)
        mine = self.list().get_json()
        theirs = self.list(headers=alice_headers, user="alice").get_json()
        self.assertEqual([s["label"] for s in mine], ["Alice"])
        self.assertEqual([s["label"] for s in theirs], ["Testuser"])


class TestCancel(ApiTestCase):
    """DELETE /schedules/<username>/<id>"""

    def cancel(self, schedule_id, headers=None, user=USER):
        """DELETE a schedule"""
        return self.client.delete(
            f"/schedules/{user}/{schedule_id}", headers=headers or auth())

    def test_cancelled_schedule_disappears_from_the_list(self):
        """204, and the schedule is gone"""
        schedule_id = self.create().get_json()["id"]
        self.assertEqual(self.cancel(schedule_id).status_code, 204)
        self.assertEqual(self.list().get_json(), [])

    def test_cancelling_twice_gives_404(self):
        """the second time there is nothing active to cancel"""
        schedule_id = self.create().get_json()["id"]
        self.cancel(schedule_id)
        self.assertEqual(self.cancel(schedule_id).status_code, 404)

    def test_unknown_or_malformed_id_gives_404(self):
        """nothing to cancel"""
        for schedule_id in ("00000000-0000-4000-8000-000000000000", "x", "1 or 1"):
            with self.subTest(schedule_id=schedule_id):
                self.assertEqual(self.cancel(schedule_id).status_code, 404)

    def test_cannot_cancel_somebody_elses_schedule(self):
        """alice gets 404 for testuser's schedule, which keeps running"""
        schedule_id = self.create().get_json()["id"]
        resp = self.cancel(schedule_id, user="alice",
                           headers=auth(user="alice", account=ALICE["account_num"]))
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(len(self.list().get_json()), 1)
        self.assertEqual(len(self.db.due_schedules(datetime.date(2030, 1, 1))), 1)

    def test_cannot_cancel_through_somebody_elses_path(self):
        """alice's token on testuser's path is refused"""
        schedule_id = self.create().get_json()["id"]
        resp = self.cancel(schedule_id, user=USER,
                           headers=auth(user="alice", account=ALICE["account_num"]))
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(len(self.list().get_json()), 1)


class TestAuthentication(ApiTestCase):
    """Every route needs the token of the user in the path"""

    def requests_to_try(self):
        """every route, as a callable taking headers"""
        sid = "00000000-0000-4000-8000-000000000000"
        body = json.dumps({"account_num": ALICE["account_num"],
                           "amount": 100, "frequency": "weekly"})
        return {
            "list": lambda h: self.client.get(f"/schedules/{USER}", headers=h),
            "create": lambda h: self.client.post(
                f"/schedules/{USER}", headers=h, data=body),
            "cancel": lambda h: self.client.delete(
                f"/schedules/{USER}/{sid}", headers=h),
        }

    def test_no_token(self):
        """401 without Authorization"""
        for name, send in self.requests_to_try().items():
            with self.subTest(route=name):
                self.assertEqual(send({}).status_code, 401)

    def test_token_of_another_user(self):
        """401 when the token belongs to somebody else"""
        headers = auth(user="alice", account=ALICE["account_num"])
        for name, send in self.requests_to_try().items():
            with self.subTest(route=name):
                self.assertEqual(send(headers).status_code, 401)

    def test_token_signed_with_another_key(self):
        """401 for a forged token"""
        headers = {"Authorization": "Bearer " + helpers.token_for(
            key=helpers.OTHER_PRIVATE_KEY)}
        for name, send in self.requests_to_try().items():
            with self.subTest(route=name):
                self.assertEqual(send(headers).status_code, 401)

    def test_expired_token(self):
        """401 for an expired token"""
        past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
        headers = {"Authorization": "Bearer " + helpers.token_for(exp=past)}
        for name, send in self.requests_to_try().items():
            with self.subTest(route=name):
                self.assertEqual(send(headers).status_code, 401)

    def test_nothing_was_stored_without_authentication(self):
        """a refused create stores nothing"""
        self.requests_to_try()["create"]({})
        self.assertEqual(self.db.list_schedules(USER), [])


class TestProbes(ApiTestCase):
    """/ready and /version need no token"""

    def test_ready_and_version(self):
        """probes answer"""
        self.assertEqual(self.client.get("/ready").status_code, 200)
        self.assertEqual(self.client.get("/version").get_data(as_text=True), "1")


if __name__ == "__main__":
    unittest.main()
