// Copyright 2026 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * Calls to the JSON API of the Flask service. Anything but a 2xx answer
 * rejects with an ApiError that carries the HTTP status and the service's
 * message.
 */
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request(path, { method = 'GET', body } = {}) {
  const response = await fetch(path, {
    method,
    credentials: 'same-origin',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data = null;
  try {
    data = await response.json();
  } catch {
    // an answer without a JSON body (a proxy's error page, say)
  }
  if (!response.ok) {
    throw new ApiError(data?.error ?? `Request failed (${response.status})`, response.status);
  }
  return data;
}

export const getConfig = () => request('/api/config');
export const getSession = () => request('/api/session');
export const getHome = () => request('/api/home');
export const login = (credentials) => request('/api/login', { method: 'POST', body: credentials });
export const signup = (fields) => request('/api/signup', { method: 'POST', body: fields });
export const logout = () => request('/api/logout', { method: 'POST' });
export const sendPayment = (payment) => request('/api/payment', { method: 'POST', body: payment });
export const sendDeposit = (deposit) => request('/api/deposit', { method: 'POST', body: deposit });
export const sendConsent = (answer) => request('/api/consent', { method: 'POST', body: answer });
