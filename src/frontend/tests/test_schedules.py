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
Unit tests for the scheduled (recurring) payment routes of the frontend:
creating and cancelling a schedule, input validation, authentication,
and how the home page lists schedules and their failures.
"""

import json
from unittest.mock import MagicMock, patch

import jwt
from requests.exceptions import RequestException

from test_payment_deposit_handlers import HandlerTestCase, backend_response

CONTACT = {'label': 'Alice', 'account_num': '1811616161',
           'routing_num': '883745000', 'is_external': False}
EXTERNAL = {'label': 'Elsewhere Bank', 'account_num': '7777777777',
            'routing_num': '123456789', 'is_external': True}
SCHEDULE = {'id': 'sched-1', 'account_num': '1811616161', 'label': 'Alice',
            'amount': 12550, 'frequency': 'weekly',
            'next_payment_date': '2030-03-04',
            'last_status': None, 'last_attempt_date': None,
            'last_error': None}


def fake_api(contacts=None, schedules=None):
    """A replacement for ApiCall.make_call that answers per display name"""
    answers = {'contacts': contacts, 'schedules': schedules}

    def make_call(self):
        answer = answers.get(self.display_name)
        if answer is None:
            return None
        resp = MagicMock()
        resp.json.return_value = answer
        return resp
    return make_call


class ScheduleTestCase(HandlerTestCase):
    """Adds helpers for the schedule routes"""

    def setUp(self):
        super().setUp()
        self.delete = patch('frontend.requests.delete',
                            return_value=backend_response(204)).start()

    def schedule(self, **overrides):
        """Submit the schedule form"""
        form = {'account_num': '1811616161', 'amount': '12.55',
                'frequency': 'weekly'}
        form.update(overrides)
        return self.client.post('/schedules', data=form)

    def home(self, contacts=None, schedules=None):
        """Render the home page with the given backend answers"""
        with patch('frontend.ApiCall.make_call', new=fake_api(contacts, schedules)):
            return self.client.get('/home')

    def schedule_calls(self):
        """The mocked posts that went to the scheduled payments service"""
        uri = self.app.config['SCHEDULES_URI']
        return [c for c in self.post.call_args_list
                if c.kwargs['url'].startswith(uri)]


class TestScheduleAuthentication(ScheduleTestCase):
    """Only signed in users manage schedules"""

    def test_create_without_token_is_unauthorized(self):
        """no token cookie gives 401 and nothing is sent"""
        self.client.delete_cookie('token')
        self.assertEqual(self.schedule().status_code, 401)
        self.post.assert_not_called()

    def test_cancel_without_token_is_unauthorized(self):
        """no token cookie gives 401 and nothing is sent"""
        self.client.delete_cookie('token')
        resp = self.client.post('/schedules/sched-1/cancel')
        self.assertEqual(resp.status_code, 401)
        self.delete.assert_not_called()

    def test_invalid_token_is_unauthorized(self):
        """a token that fails verification gives 401 and nothing is sent"""
        with patch('frontend.jwt.decode',
                   side_effect=jwt.exceptions.InvalidTokenError):
            self.assertEqual(self.schedule().status_code, 401)
            resp = self.client.post('/schedules/sched-1/cancel')
            self.assertEqual(resp.status_code, 401)
        self.post.assert_not_called()
        self.delete.assert_not_called()


class TestCreateSchedule(ScheduleTestCase):
    """Creating a schedule"""

    def test_sends_schedule_to_the_service(self):
        """the amount is sent in cents with the user's token"""
        resp = self.schedule(frequency='monthly')
        self.assertEqual(resp.status_code, 303)
        self.assertIn('Scheduled+payment+created', resp.headers['Location'])
        calls = self.schedule_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].kwargs['url'],
                         self.app.config['SCHEDULES_URI'] + '/testuser')
        self.assertEqual(self.sent(calls[0]),
                         {'account_num': '1811616161', 'amount': 1255,
                          'frequency': 'monthly'})
        self.assertEqual(calls[0].kwargs['headers']['Authorization'],
                         'Bearer abc')

    def test_rejects_bad_frequency(self):
        """only weekly and monthly are accepted"""
        resp = self.schedule(frequency='daily')
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b'Scheduled payment failed', resp.data)
        self.post.assert_not_called()

    def test_rejects_bad_amounts(self):
        """zero, negative, too precise and non-numeric amounts"""
        for amount in ('0', '-5', '1.005', 'abc', ''):
            with self.subTest(amount=amount):
                resp = self.schedule(amount=amount)
                self.assertEqual(resp.status_code, 400)
                self.assertIn(b'Scheduled payment failed', resp.data)
        self.post.assert_not_called()

    def test_rejects_missing_fields(self):
        """a form without the recipient is refused"""
        resp = self.client.post('/schedules', data={'amount': '5',
                                                    'frequency': 'weekly'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b'missing form field', resp.data)
        self.post.assert_not_called()

    def test_service_rejection_is_shown(self):
        """a 400 from the service (e.g. not a contact) is shown to the user"""
        self.post.return_value = backend_response(
            400, 'recipient is not one of your contacts')
        resp = self.schedule(account_num='9999999999')
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b'recipient is not one of your contacts', resp.data)

    def test_service_error_is_a_bad_gateway(self):
        """a 5xx from the service gives 502"""
        self.post.return_value = backend_response(500, 'boom')
        self.assertEqual(self.schedule().status_code, 502)

    def test_service_unreachable_is_a_bad_gateway(self):
        """a connection failure gives 502"""
        self.post.side_effect = RequestException
        resp = self.schedule()
        self.assertEqual(resp.status_code, 502)
        self.assertIn(b'Scheduled payment failed', resp.data)


class TestCancelSchedule(ScheduleTestCase):
    """Cancelling a schedule"""

    def test_cancel_calls_delete_and_redirects(self):
        """the schedule id is deleted for the signed in user"""
        resp = self.client.post('/schedules/sched-1/cancel')
        self.assertEqual(resp.status_code, 303)
        self.assertIn('Scheduled+payment+cancelled', resp.headers['Location'])
        self.delete.assert_called_once()
        kwargs = self.delete.call_args.kwargs
        self.assertEqual(kwargs['url'],
                         self.app.config['SCHEDULES_URI'] + '/testuser/sched-1')
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer abc')

    def test_schedule_id_cannot_change_the_path(self):
        """special characters in the id are escaped"""
        self.client.post('/schedules/a%3Fb/cancel')
        self.assertTrue(self.delete.call_args.kwargs['url'].endswith('/testuser/a%3Fb'))

    def test_unknown_schedule_is_shown_as_failure(self):
        """a 404 from the service is reported, not hidden"""
        self.delete.return_value = backend_response(404, 'no such schedule')
        resp = self.client.post('/schedules/nope/cancel')
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b'Cancelling the scheduled payment failed', resp.data)

    def test_service_unreachable_is_a_bad_gateway(self):
        """a connection failure gives 502"""
        self.delete.side_effect = RequestException
        self.assertEqual(self.client.post('/schedules/sched-1/cancel').status_code, 502)


class TestHomeSchedules(ScheduleTestCase):
    """The home page form and list"""

    def test_form_offers_only_internal_contacts(self):
        """the recipient select lists the user's own-bank contacts"""
        html = self.home(contacts=[CONTACT, EXTERNAL], schedules=[]).data.decode()
        self.assertIn('id="schedule-form"', html)
        select = html.split('id="schedule-account"')[1].split('</select>')[0]
        self.assertIn('Alice', select)
        self.assertNotIn('Elsewhere Bank', select)
        self.assertIn('value="weekly"', html)
        self.assertIn('value="monthly"', html)

    def test_empty_list(self):
        """no schedules shows a hint"""
        html = self.home(contacts=[CONTACT], schedules=[]).data.decode()
        self.assertIn('No Scheduled Payments', html)

    def test_unavailable_service_is_reported(self):
        """if the schedules cannot be loaded the page says so"""
        resp = self.home(contacts=[CONTACT], schedules=None)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Could Not Load Scheduled Payments', resp.data)

    def test_lists_schedule_details(self):
        """contact, amount, frequency, next date and a cancel button"""
        html = self.home(contacts=[CONTACT], schedules=[SCHEDULE]).data.decode()
        row = html.split('data-schedule-id="sched-1"')[1].split('</tr>')[0]
        self.assertIn('Alice', row)
        self.assertIn('$125.50', row)
        self.assertIn('Weekly', row)
        self.assertIn('Mar 04, 2030', row)
        self.assertIn('action="/schedules/sched-1/cancel"', row)
        self.assertNotIn('schedule-failure', row)

    def test_failure_is_shown_next_to_the_schedule(self):
        """the last failed payment and its reason are visible"""
        failed = dict(SCHEDULE, last_status='failed',
                      last_attempt_date='2030-02-25',
                      last_error='insufficient balance')
        html = self.home(contacts=[CONTACT], schedules=[failed]).data.decode()
        row = html.split('data-schedule-id="sched-1"')[1].split('</tr>')[0]
        self.assertIn('schedule-failure', row)
        self.assertIn('failed: insufficient balance', row)
        self.assertIn('Feb 25, 2030', row)

    def test_schedule_fields_are_escaped(self):
        """a hostile label cannot inject markup"""
        evil = dict(SCHEDULE, label='<script>alert(1)</script>')
        html = self.home(contacts=[CONTACT], schedules=[evil]).data.decode()
        self.assertNotIn('<script>alert(1)</script>', html)

    def test_home_requests_schedules_for_the_user(self):
        """the list comes from the service, for the signed in user"""
        seen = []

        def make_call(self):
            seen.append((self.display_name, self.api_request.url))
        with patch('frontend.ApiCall.make_call', new=make_call):
            self.client.get('/home')
        self.assertIn(('schedules',
                       self.app.config['SCHEDULES_URI'] + '/testuser'), seen)
        self.assertEqual(json.dumps(sorted(n for n, _ in seen)),
                         json.dumps(['balance', 'contacts', 'schedules',
                                     'transaction_list']))
