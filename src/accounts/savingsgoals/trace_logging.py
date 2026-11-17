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
Put the current OpenTelemetry trace id and span id on every log record.

The ids use the W3C traceparent formats (32 and 16 lowercase hex characters),
so a log line can be matched with a trace in X-Ray and the other way round.
Outside of an active span, both ids are all zeros.

Each service keeps its own copy of this file, because each is built as a
separate image.
"""

import logging

from opentelemetry import trace

INVALID_TRACE_ID = '0' * 32
INVALID_SPAN_ID = '0' * 16


def current_trace_ids():
    """Return (trace_id, span_id) of the active span as hex strings"""
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return INVALID_TRACE_ID, INVALID_SPAN_ID
    return format(context.trace_id, '032x'), format(context.span_id, '016x')


class TraceContextFilter(logging.Filter):  # pylint: disable=too-few-public-methods
    """Adds trace_id and span_id attributes to log records, never drops one"""

    def filter(self, record):
        record.trace_id, record.span_id = current_trace_ids()
        return True


class TraceContextFormatter(logging.Formatter):
    """
    Formatter that can use %(trace_id)s and %(span_id)s even for records that
    did not pass through a TraceContextFilter, such as the gunicorn start-up
    lines written before the app is created.
    """

    def format(self, record):
        if not hasattr(record, 'trace_id') or not hasattr(record, 'span_id'):
            TraceContextFilter().filter(record)
        return super().format(record)


def add_trace_context(*loggers):
    """
    Attach a TraceContextFilter to every handler of the given loggers, and to
    the loggers themselves. Safe to call more than once.
    """
    for logger in loggers:
        targets = [logger, *logger.handlers]
        for target in targets:
            if not any(isinstance(f, TraceContextFilter) for f in target.filters):
                target.addFilter(TraceContextFilter())
