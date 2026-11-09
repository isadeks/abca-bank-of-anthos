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
Tests that every log line of the contacts service carries the OpenTelemetry trace id and span id
"""

import io
import json
import logging
import logging.config
import os
import re
import unittest
from unittest.mock import patch, mock_open

from opentelemetry.sdk.trace import TracerProvider

from contacts.contacts import create_app
from contacts.db import ContactsDb
from trace_logging import TraceContextFilter, TraceContextFormatter, add_trace_context

LOGGING_CONF = os.path.join(os.path.dirname(__file__), '..', 'logging.conf')
ZERO_TRACE_ID = '0' * 32
ZERO_SPAN_ID = '0' * 16

BASE_ENV = {
    'VERSION': '1',
    'LOCAL_ROUTING_NUM': '123456789',
    'PUBLIC_KEY': '1',
}


def create_test_app():
    """Create the app, with no tracing and no database, as gunicorn would"""
    env = dict(BASE_ENV, ENABLE_TRACING='false')
    with patch('contacts.contacts.open', mock_open(read_data='foo')), \
            patch('os.environ', env), \
            patch('contacts.contacts.ContactsDb'):
        return create_app()


class TestTraceLogging(unittest.TestCase):
    """Log lines written through the real logging.conf and the app logger"""

    def setUp(self):
        names = ['gunicorn.error', 'contacts', '']
        saved = {n: (list(logging.getLogger(n).handlers), logging.getLogger(n).level,
                     logging.getLogger(n).propagate) for n in names}

        def restore():
            for name, (handlers, level, propagate) in saved.items():
                logger = logging.getLogger(name)
                logger.handlers, logger.level, logger.propagate = handlers, level, propagate
        self.addCleanup(restore)

        self.stream = io.StringIO()
        with patch('sys.stdout', self.stream):
            logging.config.fileConfig(LOGGING_CONF, disable_existing_loggers=False)
        self.app = create_test_app()
        # Under pytest the app is imported as a package, so Flask names its logger
        # differently from logging.conf; in production it is the configured one
        # and does not propagate to the root handler.
        self.app.logger.propagate = False
        self.addCleanup(lambda: setattr(self.app.logger, 'handlers', []))
        self.app.logger.setLevel(logging.DEBUG)
        self.stream.seek(0)
        self.stream.truncate()
        self.tracer = TracerProvider().get_tracer(__name__)

    def lines(self):
        """The JSON log lines written so far"""
        return [json.loads(line) for line in self.stream.getvalue().splitlines() if line]

    def test_line_inside_span_carries_trace_and_span_id(self):
        """a line logged in an active span has that span's ids, 32 and 16 hex characters"""
        with self.tracer.start_as_current_span('request') as span:
            self.app.logger.info('hello from a span')
            context = span.get_span_context()
        line, = self.lines()
        self.assertEqual(line['trace_id'], format(context.trace_id, '032x'))
        self.assertEqual(line['span_id'], format(context.span_id, '016x'))
        self.assertRegex(line['trace_id'], r'^[0-9a-f]{32}$')
        self.assertRegex(line['span_id'], r'^[0-9a-f]{16}$')
        self.assertIn('hello from a span', line['message'])
        self.assertEqual(line['severity'], 'INFO')

    def test_line_in_child_span_carries_child_span_id(self):
        """the span id follows the current span, the trace id stays the same"""
        with self.tracer.start_as_current_span('parent') as parent:
            with self.tracer.start_as_current_span('child') as child:
                self.app.logger.info('in child')
            self.app.logger.info('in parent')
        in_child, in_parent = self.lines()
        self.assertEqual(in_child['span_id'], format(child.get_span_context().span_id, '016x'))
        self.assertEqual(in_parent['span_id'], format(parent.get_span_context().span_id, '016x'))
        self.assertEqual(in_child['trace_id'], in_parent['trace_id'])

    def test_line_outside_span_has_zero_ids(self):
        """a line logged outside any span still formats, with zero ids"""
        self.app.logger.info('no span here')
        line, = self.lines()
        self.assertEqual(line['trace_id'], ZERO_TRACE_ID)
        self.assertEqual(line['span_id'], ZERO_SPAN_ID)
        self.assertIn('no span here', line['message'])

    def test_gunicorn_lines_format_without_the_filter(self):
        """a record that never went through the filter, like gunicorn's start-up lines, formats"""
        handler = logging.getLogger('gunicorn.error').handlers[0]
        record = logging.LogRecord('gunicorn.error', logging.INFO, __file__, 1,
                                   'Booting worker', None, None)
        line = json.loads(handler.format(record))
        self.assertEqual(line['trace_id'], ZERO_TRACE_ID)
        self.assertEqual(line['span_id'], ZERO_SPAN_ID)

    def test_gunicorn_error_logger_lines_carry_ids(self):
        """the gunicorn.error logger, which owns the handlers, is covered too"""
        with self.tracer.start_as_current_span('request') as span:
            logging.getLogger('gunicorn.error').warning('from gunicorn')
            trace_id = format(span.get_span_context().trace_id, '032x')
        line, = self.lines()
        self.assertEqual(line['trace_id'], trace_id)

    def test_filter_is_attached_to_handlers_the_app_logger_uses(self):
        """app.logger shares gunicorn's handlers, which all carry the filter"""
        handlers = self.app.logger.handlers
        self.assertTrue(handlers)
        for handler in handlers:
            self.assertTrue(any(isinstance(f, TraceContextFilter) for f in handler.filters))

    def test_database_helper_logger_carries_ids(self):
        """db helpers log through app.logger, so their lines carry the ids as well"""
        helper = ContactsDb("sqlite:///:memory:", self.app.logger)
        helper.contacts_table.create(helper.engine)
        with self.tracer.start_as_current_span('query') as span:
            helper.get_contacts('testuser')
            trace_id = format(span.get_span_context().trace_id, '032x')
        # SQL statements span several lines, so look at the raw output
        output = self.stream.getvalue()
        self.assertIn('QUERY', output)
        # (other libraries may log at the same time, e.g. instrumentation warnings)
        ids = re.findall(r'\| (?:QUERY|RESULT).*?"trace_id": "([0-9a-f]+)"', output, re.S)
        self.assertGreaterEqual(len(ids), 2)
        self.assertEqual(set(ids), {trace_id})

    def test_add_trace_context_is_idempotent(self):
        """calling it again does not stack filters"""
        add_trace_context(logging.getLogger('gunicorn.error'), self.app.logger)
        for handler in self.app.logger.handlers:
            self.assertEqual(
                len([f for f in handler.filters if isinstance(f, TraceContextFilter)]), 1)

    def test_formatter_is_the_configured_one(self):
        """logging.conf uses the trace-aware formatter"""
        handler = logging.getLogger('gunicorn.error').handlers[0]
        self.assertIsInstance(handler.formatter, TraceContextFormatter)
        self.assertTrue(re.search(r'trace_id', handler.formatter._fmt))  # pylint: disable=protected-access
