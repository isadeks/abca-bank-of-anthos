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

"""Guards the Flask upgrade (DEM-254): the locked Flask stack must not regress."""

from importlib.metadata import version


def _parse(v):
    return tuple(int(p) for p in v.split(".")[:3])


def test_flask_is_at_least_3_1_3():
    assert _parse(version("flask")) >= (3, 1, 3)


def test_werkzeug_is_at_least_3_1_9():
    assert _parse(version("werkzeug")) >= (3, 1, 9)
