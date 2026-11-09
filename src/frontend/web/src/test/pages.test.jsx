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

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App.jsx';

const config = {
  bank_name: 'Bank of Anthos',
  cymbal_logo: false,
  platform: '',
  platform_display_name: '',
  cluster_name: 'cluster',
  pod_name: 'pod',
  pod_zone: 'zone',
  default_username: 'testuser',
  default_password: 'bankofanthos',
};

const home = {
  account_id: '1111111111',
  name: 'Test',
  balance: 100000,
  history: [
    { timestamp: '2021-03-07T12:00:00.000+0000', fromAccountNum: '1111111111', toAccountNum: '2222222222', amount: 2500, accountLabel: 'Alice' },
  ],
  contacts: [
    { label: 'Alice', account_num: '2222222222', routing_num: '883745000', is_external: false },
    { label: 'My Bank', account_num: '3333333333', routing_num: '111222333', is_external: true },
  ],
};

function json(body, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status }));
}

/** Answers the calls of the app from `routes`: 'METHOD /path' -> a function giving the response. */
function mockApi(routes) {
  const calls = [];
  vi.stubGlobal('fetch', vi.fn((path, options = {}) => {
    const key = `${options.method ?? 'GET'} ${path}`;
    calls.push({ key, body: options.body ? JSON.parse(options.body) : undefined });
    const route = routes[key];
    return route ? route() : json({ error: 'not found' }, 404);
  }));
  return calls;
}

function renderApp(path = '/', flash = null) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App flash={flash} />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  window.scrollTo = vi.fn();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('signed out', () => {
  const signedOut = {
    'GET /api/config': () => json(config),
    'GET /api/session': () => json({ error: 'Not authenticated' }, 401),
  };

  it('shows the login form with the demo credentials', async () => {
    mockApi(signedOut);
    renderApp('/');
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument();
    expect(document.querySelector('#login-username')).toHaveValue('testuser');
    expect(document.querySelector('#login-password')).toHaveValue('bankofanthos');
  });

  it('sends a signed out visitor of the home page to the login', async () => {
    mockApi(signedOut);
    renderApp('/home');
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('shows a banner when the login fails', async () => {
    mockApi({ ...signedOut, 'POST /api/login': () => json({ error: 'Login failed' }, 401) });
    renderApp('/login');
    await userEvent.click(await screen.findByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Login failed');
    expect(document.querySelector('#alertBanner')).toBeInTheDocument();
  });

  it('logs in and shows the home page', async () => {
    let signedIn = false;
    const calls = mockApi({
      'GET /api/config': () => json(config),
      'GET /api/session': () => (signedIn ? json({ name: 'Test', account_id: '1111111111' }) : json({}, 401)),
      'POST /api/login': () => {
        signedIn = true;
        return json({ redirect: '/home' });
      },
      'GET /api/home': () => json(home),
    });
    renderApp('/login');
    await userEvent.click(await screen.findByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('$1,000.00')).toBeInTheDocument();
    expect(calls.find((call) => call.key === 'POST /api/login').body).toEqual({
      username: 'testuser',
      password: 'bankofanthos',
    });
  });

  it('does not create an account when the passwords differ', async () => {
    const calls = mockApi(signedOut);
    renderApp('/signup');
    await userEvent.type(await screen.findByLabelText('Username'), 'newuser');
    await userEvent.type(document.querySelector('#signup-password'), 'one');
    await userEvent.type(document.querySelector('#signup-password-repeat'), 'two');
    await userEvent.type(document.querySelector('#signup-firstname'), 'New');
    await userEvent.type(document.querySelector('#signup-lastname'), 'User');
    await userEvent.type(document.querySelector('#signup-birthday'), '1990-01-01');
    await userEvent.click(screen.getByRole('button', { name: 'Create Account' }));
    expect(document.querySelector('#alertBanner')).not.toHaveClass('hidden');
    expect(calls.some((call) => call.key === 'POST /api/signup')).toBe(false);
  });

  it('creates an account with the time zone offset', async () => {
    let signedIn = false;
    const calls = mockApi({
      'GET /api/config': () => json(config),
      'GET /api/session': () => (signedIn ? json({ name: 'New', account_id: '1111111111' }) : json({}, 401)),
      'POST /api/signup': () => {
        signedIn = true;
        return json({ redirect: '/home' });
      },
      'GET /api/home': () => json(home),
    });
    renderApp('/signup');
    await userEvent.type(await screen.findByLabelText('Username'), 'newuser');
    await userEvent.type(document.querySelector('#signup-password'), 'secret');
    await userEvent.type(document.querySelector('#signup-password-repeat'), 'secret');
    await userEvent.type(document.querySelector('#signup-firstname'), 'New');
    await userEvent.type(document.querySelector('#signup-lastname'), 'User');
    await userEvent.type(document.querySelector('#signup-birthday'), '1990-01-01');
    await userEvent.click(screen.getByRole('button', { name: 'Create Account' }));
    await screen.findByText('$1,000.00');
    const { body } = calls.find((call) => call.key === 'POST /api/signup');
    expect(body).toMatchObject({ username: 'newuser', timezone: '-5', state: 'NY', birthday: '1990-01-01' });
  });
});

describe('signed in', () => {
  const signedIn = {
    'GET /api/config': () => json(config),
    'GET /api/session': () => json({ name: 'Test', account_id: '1111111111' }),
    'GET /api/home': () => json(home),
  };

  it('shows the account, the balance and the history', async () => {
    mockApi(signedIn);
    renderApp('/home');
    expect(await screen.findByText('1111111111')).toBeInTheDocument();
    expect(document.querySelector('#current-balance')).toHaveTextContent('$1,000.00');
    expect(document.querySelector('#transaction-table')).toHaveTextContent('Alice');
    expect(document.querySelector('#account-user-name')).toHaveTextContent('Test');
  });

  it('shows the message of a failed form post', async () => {
    mockApi(signedIn);
    renderApp('/home', { message: 'Error: Payment failed', isError: true });
    expect(await screen.findByRole('alert')).toHaveTextContent('Error: Payment failed');
  });

  it('sends a payment to a contact and shows the outcome', async () => {
    const calls = mockApi({ ...signedIn, 'POST /api/payment': () => json({ message: 'Payment successful' }) });
    renderApp('/home');
    await userEvent.click(await screen.findByText('Send Payment'));
    await userEvent.type(document.querySelector('#payment-amount'), '12.50');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(await screen.findByText('Payment successful')).toBeInTheDocument();
    const { body } = calls.find((call) => call.key === 'POST /api/payment');
    expect(body).toMatchObject({ account_num: '2222222222', amount: '12.5' });
    expect(body.uuid).toBeTruthy();
    expect(document.querySelector('#sendPayment')).not.toHaveClass('show');
  });

  it('asks for the number of a new recipient', async () => {
    const calls = mockApi({ ...signedIn, 'POST /api/payment': () => json({ message: 'Payment successful' }) });
    renderApp('/home');
    await userEvent.click(await screen.findByText('Send Payment'));
    await userEvent.selectOptions(document.querySelector('#payment-accounts'), 'add');
    expect(document.querySelector('#otherAccountInputs')).not.toHaveClass('hidden');
    await userEvent.type(document.querySelector('#payment-amount'), '5');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(document.querySelector('#payment-form')).toHaveClass('was-validated');
    expect(calls.some((call) => call.key === 'POST /api/payment')).toBe(false);
  });

  it('shows the reason when a deposit is rejected', async () => {
    mockApi({ ...signedIn, 'POST /api/deposit': () => json({ error: 'Error: Deposit failed' }, 400) });
    renderApp('/home');
    await userEvent.click(await screen.findByText('Deposit Funds'));
    await userEvent.type(document.querySelector('#deposit-amount'), '20');
    await userEvent.click(screen.getByRole('button', { name: 'Deposit' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Error: Deposit failed');
  });

  it('deposits from a saved external account', async () => {
    const calls = mockApi({ ...signedIn, 'POST /api/deposit': () => json({ message: 'Deposit successful' }) });
    renderApp('/home');
    await userEvent.click(await screen.findByText('Deposit Funds'));
    await userEvent.type(document.querySelector('#deposit-amount'), '20');
    await userEvent.click(screen.getByRole('button', { name: 'Deposit' }));
    expect(await screen.findByText('Deposit successful')).toBeInTheDocument();
    const { body } = calls.find((call) => call.key === 'POST /api/deposit');
    expect(JSON.parse(body.account)).toEqual({ account_num: '3333333333', routing_num: '111222333' });
  });

  it('signs out', async () => {
    const calls = mockApi({ ...signedIn, 'POST /api/logout': () => json({ redirect: '/login' }) });
    renderApp('/home');
    await userEvent.click(await screen.findByText('Test'));
    await userEvent.click(screen.getByText('Sign out'));
    await waitFor(() => expect(calls.some((call) => call.key === 'POST /api/logout')).toBe(true));
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument();
  });
});
