# Copyright 2021 Google LLC
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

# Use the official Python docker container, slim version, running Debian
FROM python:3.14.7-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6 AS base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

FROM base AS builder

# Set working directory
WORKDIR /app

# Install dependencies.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM base

# Set our working directory
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# show python logs as they occur
ENV PYTHONUNBUFFERED=0

# the root filesystem is read-only: do not try to write .pyc files next to the code
ENV PYTHONDONTWRITEBYTECODE=1

# explicitly set a fallback log level in case no log level is defined by Kubernetes
ENV LOG_LEVEL=info

# Add application code.
COPY . .

# Ensure files are readable for non-root users
RUN find . -type f -name '*' -exec chmod a+r '{}' ';'

# Run as a fixed non-root user (uid/gid 1000, matching the manifests' runAsUser/runAsGroup).
# The code and virtualenv are only read at runtime; writable paths are the mounted /tmp.
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid 1000 --no-create-home --shell /usr/sbin/nologin app
USER 1000:1000

# Start server using gunicorn
CMD gunicorn -b :$PORT --threads 4 --log-config logging.conf --log-level=$LOG_LEVEL "frontend:create_app()"
