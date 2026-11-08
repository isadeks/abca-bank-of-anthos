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
Integration tests for the budgets service against the real accounts-db
(Postgres with the Bank of Anthos schema and demo data).
"""

import jwt
from sqlalchemy import text


def test_budget_is_unset_for_a_new_user(client, user, auth_header):
    """A user that never set a budget has no limit."""
    username, _ = user

    response = client.get('/budget/' + username, headers=auth_header)

    assert response.status_code == 200
    assert response.get_json() == {'limit_cents': None}


def test_set_budget_is_returned(client, user, auth_header):
    """A limit set with PUT is returned by GET, in whole cents."""
    username, _ = user

    put = client.put('/budget/' + username, json={'limit_cents': 123456}, headers=auth_header)
    assert put.status_code == 200
    assert put.get_json() == {'limit_cents': 123456}

    got = client.get('/budget/' + username, headers=auth_header)
    assert got.status_code == 200
    assert got.get_json() == {'limit_cents': 123456}


def test_setting_again_updates_the_single_row(client, budgets_db, user, auth_header):
    """The upsert replaces the limit; there is one row per user."""
    username, _ = user
    client.put('/budget/' + username, json={'limit_cents': 1000}, headers=auth_header)
    client.put('/budget/' + username, json={'limit_cents': 2500}, headers=auth_header)

    assert client.get('/budget/' + username, headers=auth_header).get_json() == {
        'limit_cents': 2500}
    with budgets_db.engine.connect() as conn:
        count = conn.execute(
            text('SELECT COUNT(*) FROM budgets WHERE username = :u'), u=username).scalar()
    assert count == 1


def test_clear_budget(client, user, auth_header):
    """DELETE removes the limit, and clearing twice is harmless."""
    username, _ = user
    client.put('/budget/' + username, json={'limit_cents': 5000}, headers=auth_header)

    assert client.delete('/budget/' + username, headers=auth_header).status_code == 204
    assert client.delete('/budget/' + username, headers=auth_header).status_code == 204
    assert client.get('/budget/' + username, headers=auth_header).get_json() == {
        'limit_cents': None}


def test_budget_survives_a_restart(client, make_client, user, auth_header):
    """A new service instance (a restart) still reads what the old one stored."""
    username, _ = user
    client.put('/budget/' + username, json={'limit_cents': 77700}, headers=auth_header)

    restarted = make_client()

    assert restarted.get('/budget/' + username, headers=auth_header).get_json() == {
        'limit_cents': 77700}


def test_budgets_are_per_user(client, budgets_db, user, auth_header):
    """One user's budget is not stored for others."""
    username, _ = user
    client.put('/budget/' + username, json={'limit_cents': 9900}, headers=auth_header)

    assert budgets_db.get_budget(username) == 9900
    assert budgets_db.get_budget('testuser') != 9900


def test_other_users_budget_is_denied(client, user, auth_header):
    """A valid token does not give access to another user's budget."""
    username, _ = user
    client.put('/budget/' + username, json={'limit_cents': 9900}, headers=auth_header)

    assert client.get('/budget/testuser', headers=auth_header).status_code == 401
    assert client.put('/budget/testuser', json={'limit_cents': 1},
                      headers=auth_header).status_code == 401
    assert client.delete('/budget/testuser', headers=auth_header).status_code == 401


def test_budget_for_unknown_user_is_rejected_by_the_schema(client, keys):
    """budgets.username is a foreign key to users.username."""
    token = jwt.encode({'user': 'it_nobody_here', 'acct': '1000000000'}, keys['private'],
                       algorithm='RS256')

    response = client.put(
        '/budget/it_nobody_here', headers={'Authorization': 'Bearer ' + token},
        json={'limit_cents': 5000})

    assert response.status_code == 500
