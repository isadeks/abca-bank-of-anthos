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
Tests for the frontend's OpenTelemetry (OTLP + W3C trace context) setup
"""

import http.server
import os
import threading
import unittest
from unittest.mock import MagicMock, patch, mock_open

from opentelemetry import trace
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from requests.exceptions import RequestException

import frontend
from api_call import ApiCall, ApiRequest
from traced_thread_pool_executor import TracedThreadPoolExecutor

BASE_ENV = {
    'VERSION': '1',
    'PUB_KEY_PATH': '1',
    'METADATA_SERVER': 'metadata.invalid',
}

# The SDK reads these from the real os.environ object, which patching
# 'os.environ' with a new dict does not reach, so they are patched in place.
OTEL_ENV = {
    'OTEL_SERVICE_NAME': 'frontend',
    'OTEL_RESOURCE_ATTRIBUTES': 'k8s.namespace.name=pr-7',
}


def create_app_with_tracing(enable):
    """Create the app with the tracing libraries mocked, return the mocks"""
    env = dict(BASE_ENV, ENABLE_TRACING=enable)
    with patch.dict(os.environ, OTEL_ENV), \
            patch('frontend.open', mock_open(read_data='foo')), \
            patch('os.environ', env), \
            patch('frontend.requests.get', side_effect=RequestException), \
            patch('frontend.OTLPSpanExporter') as exporter, \
            patch('frontend.set_global_textmap') as set_textmap, \
            patch('frontend.FlaskInstrumentor') as flask_instr, \
            patch('frontend.RequestsInstrumentor') as requests_instr, \
            patch('frontend.Jinja2Instrumentor') as jinja_instr, \
            patch('frontend.trace') as mock_trace:
        provider = None
        mock_trace.set_tracer_provider.side_effect = \
            lambda p: mock_trace.get_tracer_provider.configure_mock(return_value=p)
        app = frontend.create_app()
        if mock_trace.set_tracer_provider.called:
            provider = mock_trace.set_tracer_provider.call_args[0][0]
    return {
        'app': app, 'provider': provider, 'exporter': exporter,
        'set_textmap': set_textmap, 'flask': flask_instr,
        'requests': requests_instr, 'jinja': jinja_instr,
    }


class TestFrontendTracingSetup(unittest.TestCase):
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
            mocks['requests'].return_value.instrument.assert_called_once_with()
            mocks['jinja'].return_value.instrument.assert_called_once_with()
        finally:
            mocks['provider'].shutdown()

    def test_tracing_enabled_resource_comes_from_otel_env(self):
        """service.name and k8s.namespace.name are taken from OTEL_* env vars"""
        mocks = create_app_with_tracing('true')
        try:
            attributes = mocks['provider'].resource.attributes
            self.assertEqual(attributes['service.name'], 'frontend')
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
        mocks['requests'].assert_not_called()


class _RecordingHandler(http.server.BaseHTTPRequestHandler):
    """Stores the headers of every request received"""
    received = []

    def do_GET(self):  # pylint: disable=invalid-name
        """Record headers and answer 200"""
        _RecordingHandler.received.append(dict(self.headers))
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'{}')

    def log_message(self, *args):  # pylint: disable=arguments-differ
        """Keep test output quiet"""


class TestTraceHeaderPropagation(unittest.TestCase):
    """Backend calls made from worker threads carry the W3C traceparent header"""

    def setUp(self):
        _RecordingHandler.received = []
        self.server = http.server.HTTPServer(('127.0.0.1', 0), _RecordingHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.exporter = InMemorySpanExporter()
        self.provider = TracerProvider()
        self.provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        RequestsInstrumentor().instrument(tracer_provider=self.provider)

    def tearDown(self):
        RequestsInstrumentor().uninstrument()
        self.server.shutdown()
        self.server.server_close()

    def test_worker_thread_calls_carry_traceparent_of_current_trace(self):
        """ApiCall.make_call in TracedThreadPoolExecutor joins the caller's trace"""
        url = f'http://127.0.0.1:{self.server.server_port}/balances/1'
        api_calls = [
            ApiCall(display_name=name,
                    api_request=ApiRequest(url=url, headers={}, timeout=4),
                    logger=MagicMock())
            for name in ('balance', 'history', 'contacts')
        ]
        tracer = self.provider.get_tracer(__name__)
        with tracer.start_as_current_span('request') as parent:
            with TracedThreadPoolExecutor(tracer, max_workers=3) as executor:
                futures = [executor.submit(call.make_call) for call in api_calls]
                for future in futures:
                    self.assertEqual(future.result().status_code, 200)
            trace_id = parent.get_span_context().trace_id

        self.assertEqual(len(_RecordingHandler.received), 3)
        for headers in _RecordingHandler.received:
            header = {k.lower(): v for k, v in headers.items()}['traceparent']
            version, header_trace_id, _span_id, flags = header.split('-')
            self.assertEqual(version, '00')
            self.assertEqual(int(header_trace_id, 16), trace_id)
            self.assertTrue(int(flags, 16) & 1, 'sampled flag is set')

    def test_worker_thread_does_not_keep_context_after_task(self):
        """A pooled worker thread is clean again once its task has finished"""
        tracer = self.provider.get_tracer(__name__)
        current_spans = []

        def current_span():
            return trace.get_current_span().get_span_context().is_valid

        with TracedThreadPoolExecutor(tracer, max_workers=1) as executor:
            with tracer.start_as_current_span('request'):
                current_spans.append(executor.submit(current_span).result())
            # same worker thread, submitted outside any span
            current_spans.append(executor.submit(current_span).result())

        self.assertEqual(current_spans, [True, False])
