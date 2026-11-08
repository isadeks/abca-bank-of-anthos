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
Tests for the contacts OpenTelemetry (OTLP + W3C trace context) setup
"""

import os
import unittest
from unittest.mock import patch, mock_open

from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from contacts.contacts import create_app

BASE_ENV = {
    'VERSION': '1',
    'LOCAL_ROUTING_NUM': '123456789',
    'PUBLIC_KEY': '1',
}

# The SDK reads these from the real os.environ object, which patching
# 'os.environ' with a new dict does not reach, so they are patched in place.
OTEL_ENV = {
    'OTEL_SERVICE_NAME': 'contacts',
    'OTEL_RESOURCE_ATTRIBUTES': 'k8s.namespace.name=pr-7',
}


def create_app_with_tracing(enable):
    """Create the app with the tracing libraries mocked, return the mocks"""
    env = dict(BASE_ENV, ENABLE_TRACING=enable)
    with patch.dict(os.environ, OTEL_ENV), \
            patch('contacts.contacts.open', mock_open(read_data='foo')), \
            patch('os.environ', env), \
            patch('contacts.contacts.ContactsDb'), \
            patch('contacts.contacts.OTLPSpanExporter') as exporter, \
            patch('contacts.contacts.set_global_textmap') as set_textmap, \
            patch('contacts.contacts.FlaskInstrumentor') as flask_instr, \
            patch('contacts.contacts.trace') as mock_trace:
        mock_trace.set_tracer_provider.side_effect = \
            lambda p: mock_trace.get_tracer_provider.configure_mock(return_value=p)
        app = create_app()
        provider = None
        if mock_trace.set_tracer_provider.called:
            provider = mock_trace.set_tracer_provider.call_args[0][0]
    return {
        'app': app, 'provider': provider, 'exporter': exporter,
        'set_textmap': set_textmap, 'flask': flask_instr,
    }


class TestContactsTracing(unittest.TestCase):
    """Tests how create_app wires up tracing"""

    def test_tracing_enabled_uses_otlp_exporter_and_w3c_propagator(self):
        """spans go to an OTLP exporter configured from OTEL_* env, W3C propagator is set"""
        mocks = create_app_with_tracing('true')
        try:
            # exporter is built without arguments: the endpoint comes from OTEL_* env vars
            mocks['exporter'].assert_called_once_with()
            propagator = mocks['set_textmap'].call_args[0][0]
            self.assertIsInstance(propagator, TraceContextTextMapPropagator)
            mocks['flask'].return_value.instrument_app.assert_called_once_with(mocks['app'])
        finally:
            mocks['provider'].shutdown()

    def test_tracing_enabled_resource_comes_from_otel_env(self):
        """service.name and k8s.namespace.name are taken from OTEL_* env vars"""
        mocks = create_app_with_tracing('true')
        try:
            attributes = mocks['provider'].resource.attributes
            self.assertEqual(attributes['service.name'], 'contacts')
            self.assertEqual(attributes['k8s.namespace.name'], 'pr-7')
        finally:
            mocks['provider'].shutdown()

    def test_tracing_disabled_sets_up_nothing(self):
        """ENABLE_TRACING=false leaves the exporter and instrumentation off"""
        mocks = create_app_with_tracing('false')
        self.assertIsNone(mocks['provider'])
        mocks['exporter'].assert_not_called()
        mocks['set_textmap'].assert_not_called()
        mocks['flask'].assert_not_called()
