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
Tests for the payment runner: paying what is due, protection against paying
twice, failure handling, and cancelled schedules.
"""

import datetime
import json
import logging
import unittest
from unittest.mock import MagicMock

import jwt
import requests

import db
from worker import PaymentRunner, payment_id
from signing import PaymentTokenSigner
from scheduledpayments.tests import helpers
from scheduledpayments.tests.helpers import ALICE, BOB, ACCOUNT, USER

UTC = datetime.timezone.utc
D = datetime.date
TRANSACTIONS = "http://ledgerwriter:8080/transactions"


def at(day, hour=9):
    """A moment on the given date"""
    return datetime.datetime(day.year, day.month, day.day, hour, tzinfo=UTC)


def ledger_response(status, text=""):
    """A fake answer of ledgerwriter"""
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    return resp


class RunnerTestCase(unittest.TestCase):
    """A runner on an in-memory database with the ledger mocked"""

    def setUp(self):
        self.db = helpers.make_db()
        self.ledger = MagicMock(return_value=ledger_response(201, "ok"))
        self.runner = self.make_runner()

    def make_runner(self, **kwargs):
        """A runner sharing this test's database and ledger"""
        return PaymentRunner(
            self.db, PaymentTokenSigner(helpers.PRIVATE_KEY), TRANSACTIONS,
            helpers.LOCAL_ROUTING, logging.getLogger("test"),
            post=self.ledger, **kwargs)

    def add(self, due=D(2026, 4, 7), frequency="weekly", amount=2500,
            to=ALICE, user=USER, account=ACCOUNT, anchor=None):
        """Store a schedule whose next payment is on `due`"""
        return self.db.create_schedule({
            "username": user, "from_account_num": account,
            "to_account_num": to["account_num"], "to_label": to["label"],
            "amount_cents": amount, "frequency": frequency,
            "anchor_day": anchor or due.day, "next_payment_date": due})

    def schedule(self, schedule_id):
        """The current state of a schedule (active ones only)"""
        return next(s for s in self.db.due_schedules(D(9999, 1, 1))
                    if s["schedule_id"] == schedule_id)

    def sent(self, index=-1):
        """The JSON body of a payment sent to the ledger"""
        return json.loads(self.ledger.call_args_list[index].kwargs["data"])


class TestPaying(RunnerTestCase):
    """Due schedules are paid through the ledger"""

    def test_pays_a_schedule_that_is_due(self):
        """the ledger gets the payment as the customer would send it"""
        schedule = self.add()
        counts = self.runner.run_once(now=at(D(2026, 4, 7)))
        self.assertEqual(counts, {"paid": 1, "failed": 0, "skipped": 0})
        self.ledger.assert_called_once()
        self.assertEqual(self.ledger.call_args.kwargs["url"], TRANSACTIONS)
        self.assertEqual(self.sent(), {
            "fromAccountNum": ACCOUNT, "fromRoutingNum": helpers.LOCAL_ROUTING,
            "toAccountNum": ALICE["account_num"],
            "toRoutingNum": helpers.LOCAL_ROUTING, "amount": 2500,
            "uuid": payment_id(schedule["schedule_id"], D(2026, 4, 7))})

    def test_payment_is_authorised_with_a_short_lived_token_of_the_customer(self):
        """the ledger can verify it, it names the customer and it expires soon"""
        self.add()
        self.runner.run_once(now=at(D(2026, 4, 7)))
        header = self.ledger.call_args.kwargs["headers"]["Authorization"]
        self.assertTrue(header.startswith("Bearer "))
        claims = jwt.decode(header[len("Bearer "):], helpers.PUBLIC_KEY,
                            algorithms="RS256", options={"verify_exp": False})
        self.assertEqual((claims["user"], claims["acct"]), (USER, ACCOUNT))
        self.assertLessEqual(claims["exp"] - claims["iat"], 60)

    def test_moves_a_weekly_schedule_a_week_on(self):
        """the next payment date advances and the success is recorded"""
        schedule = self.add()
        self.runner.run_once(now=at(D(2026, 4, 7)))
        current = self.schedule(schedule["schedule_id"])
        self.assertEqual(current["next_payment_date"], D(2026, 4, 14))
        self.assertEqual(current["last_status"], "succeeded")
        self.assertIsNone(current["last_error"])
        self.assertEqual(current["last_attempt_date"], D(2026, 4, 7))

    def test_moves_a_monthly_schedule_a_month_on(self):
        """the 31st goes to the end of the next month, then back"""
        schedule = self.add(due=D(2026, 1, 31), frequency="monthly")
        self.runner.run_once(now=at(D(2026, 1, 31)))
        self.assertEqual(self.schedule(schedule["schedule_id"])["next_payment_date"],
                         D(2026, 2, 28))
        self.runner.run_once(now=at(D(2026, 2, 28)))
        self.assertEqual(self.schedule(schedule["schedule_id"])["next_payment_date"],
                         D(2026, 3, 31))

    def test_pays_a_late_schedule(self):
        """a date that was missed is still paid"""
        self.add(due=D(2026, 4, 1))
        self.assertEqual(self.runner.run_once(now=at(D(2026, 4, 3)))["paid"], 1)

    def test_does_not_pay_before_the_date(self):
        """a schedule due tomorrow is left alone"""
        schedule = self.add(due=D(2026, 4, 8))
        counts = self.runner.run_once(now=at(D(2026, 4, 7)))
        self.assertEqual(counts, {"paid": 0, "failed": 0, "skipped": 0})
        self.ledger.assert_not_called()
        self.assertEqual(self.schedule(schedule["schedule_id"])["next_payment_date"],
                         D(2026, 4, 8))

    def test_a_pass_pays_a_schedule_once_a_day(self):
        """the schedule has moved on, so a second pass the same day pays nothing"""
        self.add()
        self.runner.run_once(now=at(D(2026, 4, 7)))
        self.runner.run_once(now=at(D(2026, 4, 7), hour=10))
        self.assertEqual(self.ledger.call_count, 1)

    def test_pays_each_schedule_of_each_customer(self):
        """two customers, three schedules"""
        self.add(to=ALICE)
        self.add(to=BOB, amount=100)
        self.add(user="alice", account=ALICE["account_num"], to=BOB)
        self.assertEqual(self.runner.run_once(now=at(D(2026, 4, 7)))["paid"], 3)
        payers = sorted(json.loads(c.kwargs["data"])["fromAccountNum"]
                        for c in self.ledger.call_args_list)
        self.assertEqual(payers, sorted([ACCOUNT, ACCOUNT, ALICE["account_num"]]))

    def test_catches_up_one_date_per_pass(self):
        """two missed weeks are paid by two passes, each with its own id"""
        self.add(due=D(2026, 3, 24))
        now = at(D(2026, 4, 7))
        self.runner.run_once(now=now)
        self.runner.run_once(now=now)
        self.runner.run_once(now=now)
        self.assertEqual(self.ledger.call_count, 3)   # Mar 24, Mar 31, Apr 7
        ids = {self.sent(i)["uuid"] for i in range(3)}
        self.assertEqual(len(ids), 3)


class TestCancelled(RunnerTestCase):
    """Cancelled schedules never run"""

    def test_cancelled_schedule_is_not_paid(self):
        """cancelled before it fell due"""
        schedule = self.add()
        self.assertTrue(self.db.cancel_schedule(USER, schedule["schedule_id"]))
        counts = self.runner.run_once(now=at(D(2026, 4, 7)))
        self.assertEqual(counts, {"paid": 0, "failed": 0, "skipped": 0})
        self.ledger.assert_not_called()

    def test_cancelled_while_the_runner_was_working(self):
        """a schedule cancelled between listing and claiming is skipped"""
        schedule = self.add()
        due = self.db.due_schedules(D(2026, 4, 7))
        self.db.cancel_schedule(USER, schedule["schedule_id"])
        result = self.db.claim_attempt(
            schedule["schedule_id"], due[0]["next_payment_date"],
            D(2026, 4, 14), at(D(2026, 4, 7)),
            datetime.timedelta(minutes=5), datetime.timedelta(minutes=50))
        self.assertEqual(result, db.SKIPPED)
        self.assertIsNone(self.db.get_attempt(schedule["schedule_id"], D(2026, 4, 7)))

    def test_cancelled_schedule_stays_cancelled_after_failures(self):
        """cancelling after a failed payment keeps it from running again"""
        schedule = self.add()
        self.ledger.return_value = ledger_response(400, "insufficient balance")
        self.runner.run_once(now=at(D(2026, 4, 7)))
        self.db.cancel_schedule(USER, schedule["schedule_id"])
        self.runner.run_once(now=at(D(2026, 4, 14)))
        self.assertEqual(self.ledger.call_count, 1)


class TestDoublePaymentProtection(RunnerTestCase):
    """A due date is paid at most once, whatever retries and restarts happen"""

    def test_two_runners_pay_once(self):
        """a second runner (another pod, or a restart) finds nothing to pay"""
        self.add()
        other = self.make_runner()
        self.runner.run_once(now=at(D(2026, 4, 7)))
        other.run_once(now=at(D(2026, 4, 7)))
        self.assertEqual(self.ledger.call_count, 1)

    def test_second_claim_of_the_same_date_is_refused(self):
        """only one claimant gets to pay a (schedule, date)"""
        schedule = self.add()
        args = (schedule["schedule_id"], D(2026, 4, 7), D(2026, 4, 14),
                at(D(2026, 4, 7)), datetime.timedelta(minutes=5),
                datetime.timedelta(minutes=50))
        self.assertEqual(self.db.claim_attempt(*args), db.CLAIMED)
        self.assertEqual(self.db.claim_attempt(*args), db.BUSY)

    def test_runner_working_on_a_payment_is_not_overtaken(self):
        """another runner during the lease does not pay"""
        schedule = self.add()
        self.db.claim_attempt(
            schedule["schedule_id"], D(2026, 4, 7), D(2026, 4, 14),
            at(D(2026, 4, 7)), datetime.timedelta(minutes=5),
            datetime.timedelta(minutes=50))
        counts = self.runner.run_once(now=at(D(2026, 4, 7)) + datetime.timedelta(minutes=2))
        self.assertEqual(counts["skipped"], 1)
        self.ledger.assert_not_called()

    def test_restart_after_a_crash_retries_with_the_same_payment_id(self):
        """a runner that died after claiming: the retry reuses the id, so the
        ledger can refuse it if the first request got through"""
        schedule = self.add()
        self.db.claim_attempt(
            schedule["schedule_id"], D(2026, 4, 7), D(2026, 4, 14),
            at(D(2026, 4, 7)), datetime.timedelta(minutes=5),
            datetime.timedelta(minutes=50))
        later = at(D(2026, 4, 7)) + datetime.timedelta(minutes=10)
        self.assertEqual(self.runner.run_once(now=later)["paid"], 1)
        self.assertEqual(self.sent()["uuid"],
                         payment_id(schedule["schedule_id"], D(2026, 4, 7)))

    def test_ledger_refusing_a_duplicate_counts_as_paid(self):
        """the earlier request had got through: success, not a failure"""
        schedule = self.add()
        self.ledger.return_value = ledger_response(400, "duplicate transaction uuid")
        counts = self.runner.run_once(now=at(D(2026, 4, 7)))
        self.assertEqual(counts["paid"], 1)
        current = self.schedule(schedule["schedule_id"])
        self.assertEqual(current["last_status"], "succeeded")
        self.assertEqual(current["next_payment_date"], D(2026, 4, 14))

    def test_gives_up_instead_of_paying_after_the_ledger_forgot_the_id(self):
        """much later, the outcome is unknown: no new payment, schedule moves on"""
        schedule = self.add()
        self.db.claim_attempt(
            schedule["schedule_id"], D(2026, 4, 7), D(2026, 4, 14),
            at(D(2026, 4, 7)), datetime.timedelta(minutes=5),
            datetime.timedelta(minutes=50))
        later = at(D(2026, 4, 7)) + datetime.timedelta(hours=3)
        counts = self.runner.run_once(now=later)
        self.assertEqual(counts["skipped"], 1)
        self.ledger.assert_not_called()
        current = self.schedule(schedule["schedule_id"])
        self.assertEqual(current["next_payment_date"], D(2026, 4, 14))
        self.assertEqual(current["last_status"], "failed")
        self.assertIn("unknown", current["last_error"])
        # and it stays that way
        self.runner.run_once(now=later)
        self.ledger.assert_not_called()

    def test_crash_after_paying_does_not_pay_the_date_again(self):
        """the payment went through but recording it failed: the next pass
        retries with the same id and records the ledger's duplicate answer"""
        schedule = self.add()
        real_finish = self.db.finish_attempt
        self.db.finish_attempt = MagicMock(side_effect=RuntimeError("db down"))
        self.runner.run_once(now=at(D(2026, 4, 7)))     # paid, not recorded
        self.assertEqual(self.ledger.call_count, 1)
        self.db.finish_attempt = real_finish
        self.ledger.return_value = ledger_response(400, "duplicate transaction uuid")
        later = at(D(2026, 4, 7)) + datetime.timedelta(minutes=10)
        self.assertEqual(self.runner.run_once(now=later)["paid"], 1)
        ids = {self.sent(i)["uuid"] for i in range(2)}
        self.assertEqual(ids, {payment_id(schedule["schedule_id"], D(2026, 4, 7))})
        self.assertEqual(self.schedule(schedule["schedule_id"])["next_payment_date"],
                         D(2026, 4, 14))

    def test_an_attempt_that_finished_never_pays_again(self):
        """even if the schedule is put back on the old date"""
        schedule = self.add()
        self.runner.run_once(now=at(D(2026, 4, 7)))
        with self.db.engine.begin() as conn:
            conn.execute(db.SCHEDULES.update().values(next_payment_date=D(2026, 4, 7)))
        self.runner.run_once(now=at(D(2026, 4, 7), hour=11))
        self.assertEqual(self.ledger.call_count, 1)
        self.assertEqual(self.schedule(schedule["schedule_id"])["next_payment_date"],
                         D(2026, 4, 14))

    def test_attempt_is_recorded(self):
        """one attempt row per paid date"""
        schedule = self.add()
        self.runner.run_once(now=at(D(2026, 4, 7)))
        attempt = self.db.get_attempt(schedule["schedule_id"], D(2026, 4, 7))
        self.assertEqual(attempt["status"], "succeeded")
        self.assertIsNone(self.db.get_attempt(schedule["schedule_id"], D(2026, 4, 14)))


class TestFailures(RunnerTestCase):
    """A failed payment is recorded and not retried before the next date"""

    def test_insufficient_balance_is_recorded_and_the_schedule_moves_on(self):
        """the reason is kept, the date advances"""
        schedule = self.add()
        self.ledger.return_value = ledger_response(400, "insufficient balance")
        counts = self.runner.run_once(now=at(D(2026, 4, 7)))
        self.assertEqual(counts, {"paid": 0, "failed": 1, "skipped": 0})
        current = self.schedule(schedule["schedule_id"])
        self.assertEqual(current["last_status"], "failed")
        self.assertEqual(current["last_error"], "insufficient balance")
        self.assertEqual(current["last_attempt_date"], D(2026, 4, 7))
        self.assertEqual(current["next_payment_date"], D(2026, 4, 14))
        attempt = self.db.get_attempt(schedule["schedule_id"], D(2026, 4, 7))
        self.assertEqual(attempt["status"], "failed")

    def test_a_failed_payment_is_not_retried_before_the_next_date(self):
        """no endless retries: later passes the same week do nothing"""
        self.add()
        self.ledger.return_value = ledger_response(400, "insufficient balance")
        self.runner.run_once(now=at(D(2026, 4, 7)))
        for day in (7, 8, 10, 13):
            self.runner.run_once(now=at(D(2026, 4, day), hour=15))
        self.assertEqual(self.ledger.call_count, 1)

    def test_tries_again_at_the_next_date_and_the_failure_clears(self):
        """a week later the payment is attempted again and can succeed"""
        schedule = self.add()
        self.ledger.return_value = ledger_response(400, "insufficient balance")
        self.runner.run_once(now=at(D(2026, 4, 7)))
        self.ledger.return_value = ledger_response(201, "ok")
        self.runner.run_once(now=at(D(2026, 4, 14)))
        self.assertEqual(self.ledger.call_count, 2)
        self.assertNotEqual(self.sent(0)["uuid"], self.sent(1)["uuid"])
        current = self.schedule(schedule["schedule_id"])
        self.assertEqual(current["last_status"], "succeeded")
        self.assertIsNone(current["last_error"])
        self.assertEqual(current["next_payment_date"], D(2026, 4, 21))

    def test_ledger_errors_are_recorded(self):
        """the reasons for each kind of failure"""
        cases = (
            (ledger_response(400, "can't send to self"), "can't send to self"),
            (ledger_response(401, "not authorized"), "the payment was not authorized"),
            (ledger_response(500, "boom"), "the payment service failed (500)"),
            (ledger_response(404, ""), "the payment was rejected (404)"),
            (requests.exceptions.ConnectionError(),
             "the payment service could not be reached"),
            (requests.exceptions.Timeout(),
             "the payment service did not answer in time; check your transaction history"),
        )
        for answer, expected in cases:
            with self.subTest(expected=expected):
                self.setUp()
                schedule = self.add()
                if isinstance(answer, Exception):
                    self.ledger.side_effect = answer
                else:
                    self.ledger.return_value = answer
                self.runner.run_once(now=at(D(2026, 4, 7)))
                current = self.schedule(schedule["schedule_id"])
                self.assertEqual(current["last_status"], "failed")
                self.assertEqual(current["last_error"], expected)
                self.assertEqual(current["next_payment_date"], D(2026, 4, 14))

    def test_long_reasons_are_cut(self):
        """a huge error body is not stored whole"""
        schedule = self.add()
        self.ledger.return_value = ledger_response(400, "x" * 5000)
        self.runner.run_once(now=at(D(2026, 4, 7)))
        self.assertEqual(len(self.schedule(schedule["schedule_id"])["last_error"]), 200)

    def test_one_failing_schedule_does_not_stop_the_others(self):
        """the next schedule is still paid"""
        first = self.add(due=D(2026, 4, 6))
        second = self.add(due=D(2026, 4, 7), to=BOB)
        self.ledger.side_effect = [ledger_response(400, "insufficient balance"),
                                   ledger_response(201, "ok")]
        counts = self.runner.run_once(now=at(D(2026, 4, 7)))
        self.assertEqual(counts, {"paid": 1, "failed": 1, "skipped": 0})
        self.assertEqual(self.schedule(first["schedule_id"])["last_status"], "failed")
        self.assertEqual(self.schedule(second["schedule_id"])["last_status"], "succeeded")

    def test_an_unexpected_error_does_not_stop_the_pass(self):
        """a bug while handling one schedule is counted and the pass goes on;
        that schedule is not moved on, so it is retried after the lease"""
        first = self.add(due=D(2026, 4, 6))
        self.add(due=D(2026, 4, 7), to=BOB)
        self.ledger.side_effect = [RuntimeError("boom"), ledger_response(201, "ok")]
        counts = self.runner.run_once(now=at(D(2026, 4, 7)))
        self.assertEqual(counts["paid"], 1)
        self.assertEqual(counts["failed"], 1)
        self.assertEqual(self.schedule(first["schedule_id"])["next_payment_date"],
                         D(2026, 4, 6))

    def test_signing_problem_is_a_recorded_failure(self):
        """a schedule that can't get a token fails visibly, without a request"""
        schedule = self.add(account="short")
        self.runner.run_once(now=at(D(2026, 4, 7)))
        self.ledger.assert_not_called()
        current = self.schedule(schedule["schedule_id"])
        self.assertEqual(current["last_status"], "failed")
        self.assertEqual(current["next_payment_date"], D(2026, 4, 14))


if __name__ == "__main__":
    unittest.main()
