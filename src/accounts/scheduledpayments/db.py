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
db manages the scheduled payments tables of the accounts database.

Two tables:
- scheduled_payments: one row per recurring payment of a customer.
- scheduled_payment_attempts: one row per (schedule, due date). Its primary
  key is what guarantees that a due date is paid at most once, however often
  the runner is restarted or retried.
"""

# pylint: disable=too-many-arguments,too-many-positional-arguments
# pylint: disable=protected-access

import datetime
import logging
import uuid

from sqlalchemy import (
    create_engine, MetaData, Table, Column, String, Integer, Date, DateTime,
    Text, CheckConstraint, ForeignKey, Index, and_, select, update, insert)
from sqlalchemy.exc import IntegrityError
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

ACTIVE = "active"
CANCELLED = "cancelled"

# Outcomes of an attempt
PENDING = "pending"
SUCCEEDED = "succeeded"
FAILED = "failed"

# Results of claim_attempt()
CLAIMED = "claimed"      # the caller must now submit the payment
BUSY = "busy"            # another runner is working on it
DONE = "done"            # the due date was already paid or has failed
SKIPPED = "skipped"      # cancelled, or the schedule moved on: do not pay

UNKNOWN_OUTCOME = ("the outcome of this payment is unknown and it was not "
                   "retried, to avoid paying twice; check your transaction "
                   "history")

METADATA = MetaData()

# The users table belongs to userservice and is never created from here; it is
# declared so that a schedule can reference its owner.
USERS = Table("users", METADATA, Column("username", String(64), primary_key=True))

SCHEDULES = Table(
    "scheduled_payments",
    METADATA,
    Column("schedule_id", String(36), primary_key=True),
    Column("username", String(64), ForeignKey("users.username"), nullable=False),
    Column("from_account_num", String(10), nullable=False),
    Column("to_account_num", String(10), nullable=False),
    Column("to_label", String(128), nullable=False),
    Column("amount_cents", Integer, nullable=False),
    Column("frequency", String(7), nullable=False),
    Column("anchor_day", Integer, nullable=False),
    Column("next_payment_date", Date, nullable=False),
    Column("status", String(9), nullable=False, default=ACTIVE),
    Column("last_status", String(9)),
    Column("last_error", Text),
    Column("last_attempt_date", Date),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("amount_cents > 0"),
    CheckConstraint("frequency IN ('weekly', 'monthly')"),
    CheckConstraint("anchor_day BETWEEN 1 AND 31"),
    CheckConstraint("status IN ('active', 'cancelled')"),
)
Index("idx_scheduled_payments_username", SCHEDULES.c.username)
Index("idx_scheduled_payments_due", SCHEDULES.c.status, SCHEDULES.c.next_payment_date)

ATTEMPTS = Table(
    "scheduled_payment_attempts",
    METADATA,
    Column("schedule_id", String(36), ForeignKey("scheduled_payments.schedule_id"),
           primary_key=True),
    Column("due_date", Date, primary_key=True),
    Column("status", String(9), nullable=False),
    Column("error", Text),
    Column("claimed_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
    CheckConstraint("status IN ('pending', 'succeeded', 'failed')"),
)


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def _aware(moment):
    """Databases without time zones (sqlite) hand back naive UTC datetimes"""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=datetime.timezone.utc)
    return moment


class ScheduleDb:
    """
    ScheduleDb provides a set of helper functions over SQLAlchemy
    to handle db operations for the scheduled payments service.
    """

    def __init__(self, uri, logger=logging, **engine_args):
        self.engine = create_engine(uri, **engine_args)
        self.logger = logger
        # Set up tracing autoinstrumentation for sqlalchemy
        SQLAlchemyInstrumentor().instrument(
            engine=self.engine,
            service="scheduledpayments",
        )

    def create_tables(self):
        """Create the tables if they do not exist yet (they are normally
        created by the accounts-db schema; this covers databases created
        before the tables were added)."""
        METADATA.create_all(
            self.engine, tables=[SCHEDULES, ATTEMPTS], checkfirst=True)

    # --- customer facing -------------------------------------------------

    def create_schedule(self, schedule):
        """Store a new schedule.

        Params: schedule - dict with username, from_account_num,
                to_account_num, to_label, amount_cents, frequency,
                anchor_day, next_payment_date
        Return: the schedule as a dict
        Raises: SQLAlchemyError if there was an issue with the database
        """
        values = dict(schedule)
        values["schedule_id"] = str(uuid.uuid4())
        values["status"] = ACTIVE
        values["created_at"] = _utcnow()
        with self.engine.begin() as conn:
            conn.execute(insert(SCHEDULES).values(values))
        return _schedule_dict(values)

    def list_schedules(self, username):
        """The active schedules of one customer, soonest payment first."""
        statement = select(SCHEDULES).where(and_(
            SCHEDULES.c.username == username,
            SCHEDULES.c.status == ACTIVE,
        )).order_by(SCHEDULES.c.next_payment_date, SCHEDULES.c.created_at)
        with self.engine.connect() as conn:
            return [_schedule_dict(row) for row in conn.execute(statement)]

    def cancel_schedule(self, username, schedule_id):
        """Cancel an active schedule of this customer.

        Return: True if it was cancelled, False if the customer has no active
                schedule with this id (it may belong to somebody else)
        """
        statement = update(SCHEDULES).where(and_(
            SCHEDULES.c.schedule_id == schedule_id,
            SCHEDULES.c.username == username,
            SCHEDULES.c.status == ACTIVE,
        )).values(status=CANCELLED)
        with self.engine.begin() as conn:
            return conn.execute(statement).rowcount == 1

    # --- runner ----------------------------------------------------------

    def due_schedules(self, today, limit=100):
        """Active schedules whose next payment date is today or earlier."""
        statement = select(SCHEDULES).where(and_(
            SCHEDULES.c.status == ACTIVE,
            SCHEDULES.c.next_payment_date <= today,
        )).order_by(SCHEDULES.c.next_payment_date).limit(limit)
        with self.engine.connect() as conn:
            return [_schedule_dict(row) for row in conn.execute(statement)]

    def claim_attempt(self, schedule_id, due_date, next_date, now, lease,
                      give_up_after):
        """Claim the right to pay one due date of a schedule.

        The row (schedule_id, due_date) can be inserted only once, so of
        several runners (or of a runner and its restarted self) only one gets
        CLAIMED for a given due date.

        A claim whose runner died before recording an outcome is handed out
        again once `lease` has passed, so that the payment is not lost: the
        payment carries the same id as before, which the ledger recognises.
        The ledger only remembers ids for a while, so after `give_up_after`
        the outcome is declared unknown and failed rather than risking a
        second payment.

        If the due date was already dealt with (paid, failed or given up) but
        the schedule did not move on, it is moved on to `next_date` here, so
        that it can never be stuck on a date that will not be paid again.

        Return: CLAIMED, BUSY, DONE or SKIPPED
        """
        try:
            return self._claim_attempt(
                schedule_id, due_date, next_date, now, lease, give_up_after)
        except IntegrityError:
            # somebody else inserted the attempt first
            return BUSY

    def _claim_attempt(self, schedule_id, due_date, next_date, now, lease,
                       give_up_after):
        with self.engine.begin() as conn:
            schedule = conn.execute(
                select(SCHEDULES).where(SCHEDULES.c.schedule_id == schedule_id)
                .with_for_update()).first()
            if (schedule is None or schedule.status != ACTIVE
                    or schedule.next_payment_date != due_date):
                return SKIPPED
            existing = conn.execute(select(ATTEMPTS).where(and_(
                ATTEMPTS.c.schedule_id == schedule_id,
                ATTEMPTS.c.due_date == due_date)).with_for_update()).first()
            if existing is None:
                conn.execute(insert(ATTEMPTS).values(
                    schedule_id=schedule_id, due_date=due_date,
                    status=PENDING, claimed_at=now))
                return CLAIMED
            if existing.status == PENDING:
                age = now - _aware(existing.claimed_at)
                if age < lease:
                    return BUSY
                if age < give_up_after:
                    conn.execute(update(ATTEMPTS).where(and_(
                        ATTEMPTS.c.schedule_id == schedule_id,
                        ATTEMPTS.c.due_date == due_date)).values(
                            claimed_at=now))
                    return CLAIMED
                existing = _give_up(conn, schedule_id, due_date, now)
            conn.execute(update(SCHEDULES).where(and_(
                SCHEDULES.c.schedule_id == schedule_id,
                SCHEDULES.c.next_payment_date == due_date)).values(
                    next_payment_date=next_date,
                    last_status=existing.status,
                    last_error=existing.error,
                    last_attempt_date=due_date))
            return DONE

    def finish_attempt(self, schedule_id, due_date, ok, error, next_date, now):
        """Record the outcome of a claimed attempt and move the schedule on
        to its next payment date, in one transaction."""
        status = SUCCEEDED if ok else FAILED
        with self.engine.begin() as conn:
            conn.execute(update(ATTEMPTS).where(and_(
                ATTEMPTS.c.schedule_id == schedule_id,
                ATTEMPTS.c.due_date == due_date,
                ATTEMPTS.c.status == PENDING)).values(
                    status=status, error=error, completed_at=now))
            conn.execute(update(SCHEDULES).where(and_(
                SCHEDULES.c.schedule_id == schedule_id,
                SCHEDULES.c.next_payment_date == due_date)).values(
                    next_payment_date=next_date,
                    last_status=status,
                    last_error=error,
                    last_attempt_date=due_date))

    def get_attempt(self, schedule_id, due_date):
        """The attempt row for one due date, as a dict, or None."""
        with self.engine.connect() as conn:
            row = conn.execute(select(ATTEMPTS).where(and_(
                ATTEMPTS.c.schedule_id == schedule_id,
                ATTEMPTS.c.due_date == due_date))).first()
        return dict(row._mapping) if row is not None else None


def _give_up(conn, schedule_id, due_date, now):
    """Mark an attempt whose outcome never became known as failed."""
    conn.execute(update(ATTEMPTS).where(and_(
        ATTEMPTS.c.schedule_id == schedule_id,
        ATTEMPTS.c.due_date == due_date)).values(
            status=FAILED, completed_at=now, error=UNKNOWN_OUTCOME))
    return conn.execute(select(ATTEMPTS).where(and_(
        ATTEMPTS.c.schedule_id == schedule_id,
        ATTEMPTS.c.due_date == due_date))).first()


def _schedule_dict(row):
    """A schedule row (or values dict) as a plain dict."""
    data = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
    return {key: data.get(key) for key in (
        "schedule_id", "username", "from_account_num", "to_account_num",
        "to_label", "amount_cents", "frequency", "anchor_day",
        "next_payment_date", "status", "last_status", "last_error",
        "last_attempt_date")}
