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
The runner that sends scheduled payments when they fall due.

On every pass it finds the active schedules whose next payment date has come,
pays each one through the ledger's payment service and moves the schedule to
its next date, a week or a month later.

- Each due date is paid at most once. Before paying, the runner claims the
  pair (schedule, due date) in the database (see ScheduleDb.claim_attempt),
  and the payment carries an id derived from that pair, so neither a retry
  nor a restart pays twice: the ledger also refuses an id it has seen.
- A payment that fails (for example for insufficient balance) is recorded
  with its reason and the schedule moves on to its next date: it is not
  retried before then.
- Cancelled schedules are never selected, and are checked again at claim time.
- If the service was down, each missed date is still paid, one per pass.
"""

import calendar
import datetime
import json
import threading
import uuid

import requests

import db

WEEKLY = "weekly"
MONTHLY = "monthly"
FREQUENCIES = (WEEKLY, MONTHLY)

DUPLICATE_MESSAGE = "duplicate transaction uuid"
# Namespace of the payment ids; any fixed UUID works, it must never change.
PAYMENT_ID_NAMESPACE = uuid.UUID("5c0f1e2a-7a54-4a6b-9a39-1f6d0a2b7c11")

# Longest failure reason kept with a schedule
MAX_ERROR_LENGTH = 200


def add_months(day, months, anchor_day):
    """The date `months` months after `day`, on the anchor day of the month,
    or on the month's last day if it is shorter."""
    month_index = day.year * 12 + (day.month - 1) + months
    year, month = divmod(month_index, 12)
    month += 1
    return datetime.date(
        year, month, min(anchor_day, calendar.monthrange(year, month)[1]))


def next_due_date(due_date, frequency, anchor_day):
    """The payment date after `due_date`.

    Weekly: seven days later. Monthly: the next month, on the day of the month
    the schedule started on (the 31st becomes the 28th, 29th or 30th in short
    months, and goes back to the 31st afterwards).
    """
    if frequency == WEEKLY:
        return due_date + datetime.timedelta(days=7)
    if frequency == MONTHLY:
        return add_months(due_date, 1, anchor_day)
    raise ValueError(f"unknown frequency: {frequency}")


def payment_id(schedule_id, due_date):
    """The stable id of the payment of one due date of one schedule."""
    return str(uuid.uuid5(
        PAYMENT_ID_NAMESPACE, f"{schedule_id}:{due_date.isoformat()}"))


class PaymentRunner:
    """Finds due schedules and pays them."""

    # pylint: disable=too-many-arguments,too-many-instance-attributes
    # pylint: disable=too-many-positional-arguments
    def __init__(self, schedule_db, signer, transactions_uri, local_routing,
                 logger, timeout=4, lease_seconds=300,
                 give_up_after_seconds=3000, post=requests.post):
        self.db = schedule_db
        self.signer = signer
        self.transactions_uri = transactions_uri
        self.local_routing = local_routing
        self.logger = logger
        self.timeout = timeout
        # a claim is retried after the lease; the ledger remembers payment ids
        # for an hour, so retries stop well before that
        self.lease = datetime.timedelta(seconds=lease_seconds)
        self.give_up_after = datetime.timedelta(seconds=give_up_after_seconds)
        self.post = post

    def run_once(self, now=None):
        """One pass over the due schedules.

        Return: a dict counting the outcomes: paid, failed, skipped
        """
        now = now or datetime.datetime.now(datetime.timezone.utc)
        today = now.date()
        counts = {"paid": 0, "failed": 0, "skipped": 0}
        for schedule in self.db.due_schedules(today):
            try:
                outcome = self._run_schedule(schedule, now)
            except Exception:  # pylint: disable=broad-except
                # one broken schedule must not stop the others
                self.logger.exception(
                    "Unexpected error running schedule %s",
                    schedule["schedule_id"])
                outcome = "failed"
            counts[outcome] += 1
        return counts

    def _run_schedule(self, schedule, now):
        schedule_id = schedule["schedule_id"]
        due_date = schedule["next_payment_date"]
        next_date = next_due_date(
            due_date, schedule["frequency"], schedule["anchor_day"])
        claim = self.db.claim_attempt(
            schedule_id, due_date, next_date, now, self.lease,
            self.give_up_after)
        if claim != db.CLAIMED:
            self.logger.debug(
                "Not paying schedule %s due %s: %s",
                schedule_id, due_date, claim)
            return "skipped"
        ok, error = self._pay(schedule, due_date)
        self.db.finish_attempt(
            schedule_id, due_date, ok, error, next_date, now)
        if ok:
            self.logger.info(
                "Paid scheduled payment %s due %s", schedule_id, due_date)
            return "paid"
        self.logger.warning(
            "Scheduled payment %s due %s failed: %s",
            schedule_id, due_date, error)
        return "failed"

    def _pay(self, schedule, due_date):
        """Submit one payment to the ledger. Return (ok, error)."""
        try:
            token = self.signer.token_for(
                schedule["username"], schedule["from_account_num"])
            body = {
                "fromAccountNum": schedule["from_account_num"],
                "fromRoutingNum": self.local_routing,
                "toAccountNum": schedule["to_account_num"],
                "toRoutingNum": self.local_routing,
                "amount": schedule["amount_cents"],
                "uuid": payment_id(schedule["schedule_id"], due_date),
            }
            resp = self.post(
                url=self.transactions_uri,
                data=json.dumps(body),
                headers={"Authorization": "Bearer " + token,
                         "content-type": "application/json"},
                timeout=self.timeout)
        except requests.exceptions.Timeout:
            return False, ("the payment service did not answer in time; "
                           "check your transaction history")
        except requests.exceptions.RequestException:
            return False, "the payment service could not be reached"
        except ValueError as err:
            return False, str(err)
        return _outcome(resp)


def _outcome(resp):
    """Translate the ledger's answer into (ok, error)."""
    message = (resp.text or "").strip()[:MAX_ERROR_LENGTH]
    if resp.status_code == 201:
        return True, None
    if resp.status_code == 400 and message == DUPLICATE_MESSAGE:
        # this very payment was already recorded by an earlier attempt
        return True, None
    if resp.status_code == 401:
        return False, "the payment was not authorized"
    if 400 <= resp.status_code < 500:
        return False, message or f"the payment was rejected ({resp.status_code})"
    return False, f"the payment service failed ({resp.status_code})"


def start_background(runner, interval_seconds):
    """Run the runner every `interval_seconds` in a daemon thread."""
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            try:
                runner.run_once()
            except Exception:  # pylint: disable=broad-except
                runner.logger.exception("Scheduled payments pass failed")
            stop.wait(interval_seconds)

    thread = threading.Thread(target=loop, name="payment-runner", daemon=True)
    thread.start()
    return stop
