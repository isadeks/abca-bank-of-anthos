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
Integration tests for favourite contacts against the real accounts-db.
"""

LOCAL_ROUTING_NUM = '883745000'


def _add(client, username, headers, label, account_num):
    response = client.post('/contacts/' + username, headers=headers, json={
        'label': label, 'account_num': account_num,
        'routing_num': LOCAL_ROUTING_NUM, 'is_external': False})
    assert response.status_code == 201


def _flags(client, username, headers):
    listed = client.get('/contacts/' + username, headers=headers).get_json()
    return {c['label']: c['is_favorite'] for c in listed}


def test_new_contact_is_not_favorite(client, user, auth_header):
    """The column defaults to off, so contacts added without it keep working."""
    username, _ = user
    _add(client, username, auth_header, 'Mom', '1033623433')

    assert _flags(client, username, auth_header) == {'Mom': False}


def test_switch_favorite_on_and_off(client, user, auth_header):
    """The flag round-trips through Postgres and only changes the chosen contact."""
    username, _ = user
    _add(client, username, auth_header, 'Mom', '1033623433')
    _add(client, username, auth_header, 'Dad', '1055757655')

    on = client.put('/contacts/' + username + '/Mom/favorite', json={'is_favorite': True},
                    headers=auth_header)
    assert on.status_code == 200
    assert _flags(client, username, auth_header) == {'Mom': True, 'Dad': False}

    off = client.put('/contacts/' + username + '/Mom/favorite', json={'is_favorite': False},
                     headers=auth_header)
    assert off.status_code == 200
    assert _flags(client, username, auth_header) == {'Mom': False, 'Dad': False}


def test_unknown_contact_is_not_found(client, user, auth_header):
    """Switching an unknown contact answers 404."""
    username, _ = user

    response = client.put('/contacts/' + username + '/Nobody/favorite',
                          json={'is_favorite': True}, headers=auth_header)

    assert response.status_code == 404


def test_demo_contacts_are_not_favorites(contacts_db):
    """The demo data leaves the setting off."""
    contacts = contacts_db.get_contacts('testuser', include_favorite=True)

    assert contacts
    assert all(c['is_favorite'] is False for c in contacts)
