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
Unit tests for the savings goals handlers and the goals section of the home page.
"""

from unittest.mock import patch

from test_payment_deposit_handlers import HandlerTestCase, backend_response

GOALS = [
    {'id': 3, 'name': 'Holiday', 'target': 50000, 'saved': 12500,
     'account_num': '7123456789'},
    {'id': 4, 'name': 'Done', 'target': 1000, 'saved': 2000,
     'account_num': '7123456780'},
]


class GoalsTestCase(HandlerTestCase):
    """HandlerTestCase with the goals service mocked"""

    def setUp(self):
        super().setUp()
        self.request = patch('frontend.requests.request',
                             return_value=backend_response(201)).start()

    def goals_uri(self):
        """Base URL of the goals service"""
        return self.app.config['GOALS_URI']


class TestGoalsOnHomePage(GoalsTestCase):
    """The home page lists the goals with a progress bar"""

    def home(self, goals):
        """Render the home page with the given goals response"""
        class FakeApiCall:
            """Only the goals call returns something"""

            def __init__(self, display_name, **_):
                self.display_name = display_name

            def make_call(self):
                """The response of this call"""
                return _Resp(goals) if self.display_name == 'goals' else None

        with patch('frontend.ApiCall', FakeApiCall):
            return self.client.get('/home')

    def test_goals_with_saved_target_and_progress(self):
        """each goal shows saved amount, target and percentage"""
        resp = self.home(GOALS)
        body = resp.get_data(as_text=True)
        self.assertIn('Holiday', body)
        self.assertIn('$125.00', body)
        self.assertIn('$500.00', body)
        self.assertIn('width: 25%', body)
        # a goal over its target is capped at 100%
        self.assertIn('width: 100%', body)
        self.assertIn('/goals/3/contribute', body)
        self.assertIn('/goals/3/delete', body)

    def test_no_goals(self):
        """an empty list shows a hint"""
        self.assertIn('id="goals-empty"', self.home([]).get_data(as_text=True))

    def test_goals_unavailable(self):
        """a failing goals service shows an error but the page loads"""
        resp = self.home(None)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Could Not Load Savings Goals', resp.get_data(as_text=True))

    def test_create_form_limits_the_name(self):
        """the form has a 40 character limit"""
        body = self.home([]).get_data(as_text=True)
        self.assertIn('id="goal-form"', body)
        self.assertIn('maxlength="40"', body)


class _Resp:
    """Minimal response with a json() method"""

    def __init__(self, data):
        self.data = data

    def json(self):
        """The decoded body"""
        return self.data


class TestCreateGoal(GoalsTestCase):
    """POST /goals"""

    def create(self, **overrides):
        """Submit the create form"""
        form = {'name': 'Holiday', 'target': '500'}
        form.update(overrides)
        return self.client.post('/goals', data=form)

    def test_creates_goal_in_cents(self):
        """the goals service gets the trimmed name and the target in cents"""
        resp = self.create(name=' Holiday ', target='500.50')
        self.assertEqual(resp.status_code, 303)
        self.assertIn('Goal+created', resp.headers['Location'])
        call = self.request.call_args
        self.assertEqual(call.args[0], 'POST')
        self.assertEqual(call.kwargs['url'], self.goals_uri() + '/testuser')
        self.assertEqual(self.sent(call),
                         {'name': 'Holiday', 'target': 50050})

    def test_name_limit(self):
        """40 characters pass, 41 are rejected before anything is sent"""
        self.assertEqual(self.create(name='a' * 40).status_code, 303)
        self.request.reset_mock()
        resp = self.create(name='a' * 41)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('40 characters or fewer', resp.get_data(as_text=True))
        self.request.assert_not_called()

    def test_invalid_input(self):
        """blank names and bad targets are rejected"""
        for overrides in ({'name': '  '}, {'target': '0'}, {'target': '-5'},
                          {'target': 'abc'}, {'target': '1.005'}):
            with self.subTest(**overrides):
                self.assertEqual(self.create(**overrides).status_code, 400)
        self.request.assert_not_called()

    def test_missing_field(self):
        """a form without a target gives 400"""
        resp = self.client.post('/goals', data={'name': 'x'})
        self.assertEqual(resp.status_code, 400)

    def test_service_rejection_is_shown(self):
        """a 4xx from the goals service is shown to the user"""
        self.request.return_value = backend_response(400, 'too many goals')
        resp = self.create()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Savings goal failed: too many goals',
                      resp.get_data(as_text=True))

    def test_requires_sign_in(self):
        """no token gives 401"""
        self.client.delete_cookie('token')
        self.assertEqual(self.create().status_code, 401)
        self.request.assert_not_called()


class TestDeleteAndContribute(GoalsTestCase):
    """POST /goals/<id>/delete and /goals/<id>/contribute"""

    def test_delete(self):
        """the goal is deleted through the goals service"""
        resp = self.client.post('/goals/3/delete')
        self.assertEqual(resp.status_code, 303)
        call = self.request.call_args
        self.assertEqual(call.args[0], 'DELETE')
        self.assertEqual(call.kwargs['url'], self.goals_uri() + '/testuser/3')

    def test_delete_unknown(self):
        """a missing goal shows the error"""
        self.request.return_value = backend_response(404, 'goal not found')
        resp = self.client.post('/goals/3/delete')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('goal not found', resp.get_data(as_text=True))

    def test_contribute(self):
        """the amount is sent in cents with the form's transaction id"""
        resp = self.client.post('/goals/3/contribute',
                                data={'amount': '25.50', 'uuid': 'u9'})
        self.assertEqual(resp.status_code, 303)
        self.assertIn('Money+moved+to+goal', resp.headers['Location'])
        call = self.request.call_args
        self.assertEqual(call.kwargs['url'],
                         self.goals_uri() + '/testuser/3/contributions')
        self.assertEqual(self.sent(call), {'amount': 2550, 'uuid': 'u9'})

    def test_contribute_invalid_amounts(self):
        """zero, negative and over-precise amounts are rejected locally"""
        for amount in ('0', '-1', '1.005', 'x'):
            with self.subTest(amount=amount):
                resp = self.client.post('/goals/3/contribute',
                                        data={'amount': amount, 'uuid': 'u'})
                self.assertEqual(resp.status_code, 400)
        self.request.assert_not_called()

    def test_contribute_more_than_balance(self):
        """the service's balance error is shown and the page keeps its status"""
        self.request.return_value = backend_response(
            400, 'amount is more than the checking balance')
        resp = self.client.post('/goals/3/contribute',
                                data={'amount': '999999', 'uuid': 'u'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('more than the checking balance',
                      resp.get_data(as_text=True))

    def test_backend_down(self):
        """an unreachable goals service gives 502"""
        import requests
        self.request.side_effect = requests.exceptions.ConnectionError
        resp = self.client.post('/goals/3/delete')
        self.assertEqual(resp.status_code, 502)
