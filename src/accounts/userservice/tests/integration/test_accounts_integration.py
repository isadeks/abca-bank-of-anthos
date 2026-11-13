# Copyright 2019 Google LLC
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
Integration tests for a user's additional accounts against the real accounts-db.
"""

from test_userservice_integration import PASSWORD, user_form


def sign_up_and_log_in(client, username):
    """Create a user and return the bearer header of their login token"""
    assert client.post('/users', data=user_form(username)).status_code == 201
    login = client.get('/login', query_string={'username': username, 'password': PASSWORD})
    assert login.status_code == 200
    return {'Authorization': 'Bearer ' + login.get_json()['token']}


def test_open_list_and_switch_account(client, users_db, new_username):
    """An opened account is listed with its own number and can be switched to"""
    headers = sign_up_and_log_in(client, new_username)
    primary = users_db.get_user(new_username)['accountid']

    opened = client.post(f'/accounts/{new_username}', data={'label': 'Savings'},
                         headers=headers)
    assert opened.status_code == 201
    savings = opened.get_json()['accountid']
    assert savings != primary

    listed = client.get(f'/accounts/{new_username}', headers=headers).get_json()
    assert [(a['accountid'], a['label']) for a in listed] == [
        (primary, 'Checking'), (savings, 'Savings')]

    switched = client.post(f'/accounts/{new_username}/token', data={'accountid': savings},
                           headers=headers)
    assert switched.status_code == 200
    assert switched.get_json()['token']


def test_another_users_account_cannot_be_switched_to(client, new_username):
    """The token endpoint only knows the caller's own accounts"""
    headers = sign_up_and_log_in(client, new_username)
    response = client.post(f'/accounts/{new_username}/token',
                           data={'accountid': '1011226111'}, headers=headers)
    assert response.status_code == 404
