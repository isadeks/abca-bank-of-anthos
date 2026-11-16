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

"""Retry with backoff and fallback telemetry for backend calls"""

import time

from opentelemetry import metrics, trace
from requests.exceptions import RequestException

RETRIES = 1
BACKOFF_SECONDS = 0.2
FALLBACK_EVENT = 'frontend.fallback_used'
FALLBACK_COUNTER = 'frontend.fallback.count'


def record_fallback(backend, reason):
    """
    Records that the frontend fell back to degraded output for a backend:
    a span event on the current span and a counter increment.
    """
    attributes = {'backend': backend, 'reason': reason}
    trace.get_current_span().add_event(FALLBACK_EVENT, attributes)
    metrics.get_meter(__name__).create_counter(
        FALLBACK_COUNTER,
        unit='1',
        description='Times the frontend served a fallback because a backend failed',
    ).add(1, attributes)


def call_with_retry(func, retries=RETRIES, backoff=BACKOFF_SECONDS):
    """
    Calls func(), retrying on a request error with exponential backoff.
    Raises the last error when all attempts fail.
    """
    for attempt in range(retries + 1):
        try:
            return func()
        except RequestException:
            if attempt == retries:
                raise
            time.sleep(backoff * (2 ** attempt))
    return None
