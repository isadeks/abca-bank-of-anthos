# Copyright 2023 Google LLC
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

"""API calls"""

from requests import get
from requests.exceptions import RequestException

from resilience import call_with_retry, record_fallback


class ApiRequest:
    """Class for defining an API request"""

    def __init__(self, url, headers, timeout):
        """Initialize an API request"""
        self.url = url
        self.headers = headers
        self.timeout = timeout


class ApiCall:
    """Class for initializing and making an API call"""

    def __init__(self, display_name, api_request, logger):
        """Initialize an API call"""
        self.display_name = display_name
        self.api_request = api_request
        self.logger = logger

    def make_call(self):
        """
        Making an API call: one retry with backoff on failure. If it still
        fails, records the fallback (span event and metric) and returns None.
        """
        def _get():
            response = get(url=self.api_request.url,
                           headers=self.api_request.headers,
                           timeout=self.api_request.timeout)
            response.raise_for_status()
            return response

        try:
            return call_with_retry(_get)
        except (RequestException, ValueError) as err:
            self.logger.error('Error getting %s: %s',
                              self.display_name, str(err))
            record_fallback(self.display_name, type(err).__name__)
        return None
