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

import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useApp } from '../AppContext.jsx';
import { getSession, login } from '../api.js';

/** The parameters of an oauth flow that the login must carry to the consent form. */
function oauthParams(search) {
  const params = new URLSearchParams(search);
  if (params.get('response_type') !== 'code') {
    return null;
  }
  const oauth = {};
  for (const name of ['response_type', 'state', 'redirect_uri', 'app_name']) {
    if (params.has(name)) {
      oauth[name] = params.get(name);
    }
  }
  return oauth;
}

export default function Login() {
  const { config, setSession } = useApp();
  const { search } = useLocation();
  const navigate = useNavigate();
  const [validated, setValidated] = useState(false);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  const params = new URLSearchParams(search);
  const message = params.get('msg');
  const oauth = oauthParams(search);
  const action = oauth ? `/login?${new URLSearchParams(oauth)}` : '/login';
  // the service redirects here with this message when a form post is rejected
  const showFailure = failed || message === 'Login Failed';

  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    setValidated(true);
    if (!form.checkValidity()) {
      return;
    }
    setBusy(true);
    try {
      const { redirect } = await login({
        username: form.elements.username.value,
        password: form.elements.password.value,
        ...oauth,
      });
      setSession(await getSession());
      setFailed(false);
      navigate(redirect);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="container">
      <div className="row mt-5 mb-5">
        {message && message !== 'Login Failed' && (
          <div className="col-md-8 offset-md-2">
            <div className="alert alert-info alert-dismissible fade show" role="alert">
              <span className="error-icon mr-2 material-icons">error</span>{message}
            </div>
          </div>
        )}
        <div className="col-lg-6 offset-lg-3">
          <div className="card">
            <div className="card-title header-body">
              <div className="text-center col-10 offset-1">
                <p className="text-uppercase text-muted secondary-text">Welcome</p>
                <h2 className="mb-4 header-title">SIGN IN</h2>
              </div>
            </div>
            <div className="card-body sign-in">
              <div className="row align-items-center mt-2">
                <div className="col-10 offset-1 mb-4">
                  {showFailure && (
                    <div id="alertBanner" className="alert alert-danger mb-4" role="alert">
                      <span className="error-icon mr-2 material-icons">error</span>Login failed.
                    </div>
                  )}
                  <form
                    id="login-form"
                    className={`needs-validation${validated ? ' was-validated' : ''}`}
                    noValidate
                    method="POST"
                    action={action}
                    onSubmit={submit}
                  >
                    <label className="text-uppercase text-muted secondary-text" htmlFor="login-username">Username</label>
                    <div className="input-group mt-2d mb-5">
                      <div className="input-group-prepend mr-2">
                        <span className="input-group-text"><span className="material-icons">account_circle</span></span>
                      </div>
                      <input
                        className="form-control"
                        type="text"
                        id="login-username"
                        name="username"
                        autoComplete="off"
                        pattern="([a-zA-Z0-9_]){2,15}"
                        defaultValue={config.default_username}
                        required
                      />
                      <div className="invalid-feedback">Please enter your username.</div>
                    </div>
                    <label className="text-uppercase text-muted secondary-text" htmlFor="login-password">Password</label>
                    <div className="input-group mt-2 mb-5">
                      <div className="input-group-prepend mr-2">
                        <span className="input-group-text"><span className="material-icons">lock</span></span>
                      </div>
                      <input
                        className="form-control"
                        type="password"
                        id="login-password"
                        name="password"
                        defaultValue={config.default_password}
                        required
                      />
                      <div className="invalid-feedback">Please enter your password.</div>
                    </div>
                    <button className="btn btn-sign-in btn-block mb-4" type="submit" disabled={busy}>Sign in</button>
                    <small className="text-uppercase secondary-text text-muted">Not registered?</small>
                    <Link to="/signup" className="btn btn-secondary btn-block mt-2 mb-4" id="create-account-btn">
                      Create an Account
                    </Link>
                  </form>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
