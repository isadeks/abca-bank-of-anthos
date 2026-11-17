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


def _contact(label, account):
    return {'label': label, 'account_num': account,
            'routing_num': LOCAL_ROUTING_NUM, 'is_external': False}


def test_new_contact_is_not_favorite(client, user, auth_header):
    """The column defaults to off."""
    username, _ = user
    client.post('/contacts/' + username, json=_contact('Mom', '1033623433'),
                headers=auth_header)

    listed = client.get('/contacts/' + username, headers=auth_header).get_json()

    assert listed == [dict(_contact('Mom', '1033623433'), is_favorite=False)]


def test_favorite_can_be_switched_on_and_off(client, user, auth_header):
    """The setting persists in Postgres and affects only the named contact."""
    username, _ = user
    client.post('/contacts/' + username, json=_contact('Mom', '1033623433'),
                headers=auth_header)
    client.post('/contacts/' + username, json=_contact('Dad', '1055757655'),
                headers=auth_header)
    url = '/contacts/' + username + '/favorite'

    on = client.put(url, json={'label': 'Mom', 'is_favorite': True}, headers=auth_header)
    assert on.status_code == 200
    favs = {c['label']: c['is_favorite']
            for c in client.get('/contacts/' + username, headers=auth_header).get_json()}
    assert favs == {'Mom': True, 'Dad': False}

    off = client.put(url, json={'label': 'Mom', 'is_favorite': False}, headers=auth_header)
    assert off.status_code == 200
    favs = {c['label']: c['is_favorite']
            for c in client.get('/contacts/' + username, headers=auth_header).get_json()}
    assert favs == {'Mom': False, 'Dad': False}


def test_unknown_contact_is_not_found(client, user, auth_header):
    """Unknown labels give 404."""
    username, _ = user
    resp = client.put('/contacts/' + username + '/favorite',
                      json={'label': 'Nobody', 'is_favorite': True}, headers=auth_header)
    assert resp.status_code == 404


def test_demo_contacts_are_not_favorites(contacts_db):
    """Demo data ships with the setting off."""
    contacts = contacts_db.get_contacts('testuser')
    assert contacts
    assert all(c['is_favorite'] is False for c in contacts)
