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

"""Monthly budget logic of the frontend.

Pure functions (monthly spend, usage, warning decision) and thin calls to the
budgets service. Amounts are whole cents, like the rest of the system.
"""

import datetime
from decimal import Decimal, DecimalException

import requests
from requests.exceptions import RequestException

TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%S.%f%z'

# Same bounds as the budgets service accepts for limit_cents
MIN_LIMIT_CENTS = 1
MAX_LIMIT_CENTS = 100_000_000_000


def _parse_timestamp(timestamp):
    """Parse a transaction timestamp, return None if it is not valid"""
    try:
        return datetime.datetime.strptime(timestamp, TIMESTAMP_FORMAT)
    except (TypeError, ValueError):
        return None


def monthly_spend(transactions, account_id, now=None):
    """Total, in cents, of the outgoing payments made in the month of now.

    Outgoing payments are the transactions sent from account_id. Incoming
    transactions, other months and transactions that cannot be read do not
    count. The month is taken in UTC. Returns 0 if transactions is None.
    """
    if not transactions:
        return 0
    now = (now or datetime.datetime.now(datetime.timezone.utc)).astimezone(
        datetime.timezone.utc)
    total = 0
    for trans in transactions:
        if trans.get('fromAccountNum') != account_id:
            continue
        if trans.get('toAccountNum') == account_id:
            continue
        stamp = _parse_timestamp(trans.get('timestamp'))
        if stamp is None:
            continue
        stamp = stamp.astimezone(datetime.timezone.utc)
        if (stamp.year, stamp.month) != (now.year, now.month):
            continue
        amount = trans.get('amount')
        if isinstance(amount, int) and not isinstance(amount, bool) and amount > 0:
            total += amount
    return total


def budget_usage(limit_cents, spent_cents):
    """Usage of a monthly budget.

    Returns None if there is no limit. Otherwise a dict with limit_cents,
    spent_cents, remaining_cents (0 when over), percent (whole number, may be
    above 100), bar_percent (percent capped at 100 for the progress bar) and
    over (True when spent is above the limit).
    """
    if not limit_cents or limit_cents <= 0:
        return None
    spent_cents = max(spent_cents or 0, 0)
    percent = int(spent_cents * 100 // limit_cents)
    return {
        'limit_cents': limit_cents,
        'spent_cents': spent_cents,
        'remaining_cents': max(limit_cents - spent_cents, 0),
        'percent': percent,
        'bar_percent': min(percent, 100),
        'over': spent_cents > limit_cents,
    }


def would_exceed(limit_cents, spent_cents, amount_cents):
    """True if paying amount_cents on top of spent_cents goes over the limit.

    Without a limit there is nothing to exceed. A payment that lands exactly
    on the limit does not exceed it.
    """
    if not limit_cents or limit_cents <= 0:
        return False
    return (spent_cents or 0) + amount_cents > limit_cents


def dollars_to_cents(text):
    """Convert a user-entered dollar amount to whole cents.

    Raises ValueError for anything that is not a positive amount with at most
    two decimals.
    """
    try:
        amount = Decimal(str(text).strip())
        if not amount.is_finite() or amount <= 0:
            raise ValueError('amount must be positive')
        if amount > MAX_LIMIT_CENTS:
            raise ValueError('amount too large')
        cents = amount * 100
        if cents != cents.to_integral_value():
            raise ValueError('at most two decimals')
        return int(cents)
    except DecimalException as err:
        raise ValueError('not a valid amount') from err


def _headers(token):
    return {'Authorization': 'Bearer ' + token,
            'content-type': 'application/json'}


def fetch_limit(budgets_uri, username, token, timeout):
    """Read the user's monthly limit from the budgets service.

    Returns (available, limit_cents). available is False when the service
    cannot be reached or fails; limit_cents is None when there is no budget.
    """
    try:
        resp = requests.get(url=f'{budgets_uri}/{username}',
                            headers=_headers(token),
                            timeout=timeout)
        resp.raise_for_status()
        limit = resp.json().get('limit_cents')
    except (RequestException, ValueError, AttributeError):
        return False, None
    if isinstance(limit, bool) or not isinstance(limit, int):
        limit = None
    return True, limit


def save_limit(budgets_uri, username, token, limit_cents, timeout):
    """Set the user's monthly limit. Returns True on success."""
    try:
        resp = requests.put(url=f'{budgets_uri}/{username}',
                            json={'limit_cents': limit_cents},
                            headers=_headers(token),
                            timeout=timeout)
        resp.raise_for_status()
        return True
    except RequestException:
        return False


def remove_limit(budgets_uri, username, token, timeout):
    """Clear the user's monthly limit. Returns True on success."""
    try:
        resp = requests.delete(url=f'{budgets_uri}/{username}',
                               headers=_headers(token),
                               timeout=timeout)
        resp.raise_for_status()
        return True
    except RequestException:
        return False
