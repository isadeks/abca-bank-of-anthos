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
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useApp } from '../AppContext.jsx';
import { getSession, signup } from '../api.js';
import { DEFAULT_STATE, DEFAULT_TIMEZONE_ID, STATES, TIMEZONES } from '../signupOptions.js';

export default function Signup() {
  const { setSession } = useApp();
  const navigate = useNavigate();
  const [validated, setValidated] = useState(false);
  const [mismatch, setMismatch] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const today = new Date().toISOString().split('T')[0];

  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = Object.fromEntries(new FormData(form).entries());
    // several time zones share an offset, so the options are told apart by id
    fields.timezone = TIMEZONES.find((zone) => String(zone.id) === fields.timezone)?.value ?? fields.timezone;
    const passwordsMatch = fields.password === fields['password-repeat'];
    setMismatch(!passwordsMatch);
    setValidated(true);
    if (!form.checkValidity() || !passwordsMatch) {
      window.scrollTo({ top: 0, behavior: 'auto' });
      return;
    }
    setBusy(true);
    try {
      const { redirect } = await signup(fields);
      setSession(await getSession().catch(() => null));
      setError(null);
      navigate(redirect);
    } catch (err) {
      setError(err.message);
      window.scrollTo({ top: 0, behavior: 'auto' });
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="container">
      <div className="row d-flex align-items-end header header-body">
        <div className="col-lg-4">
          <Link to="/login" className="btn btn-secondary">
            <span className="mr-2 material-icons arrow-back">arrow_back</span>Back
          </Link>
        </div>
        <div className="col-md-8">
          <h2 className="header-title" id="signup-title">Register a new account</h2>
        </div>
      </div>
      <div className="row mt-5 mb-5">
        <div className="col-lg-10 offset-lg-1">
          <div className="card">
            <div className="card-body">
              <div className="row mt-4">
                <div className="col-10 offset-1 mb-2">
                  <form
                    id="signup-form"
                    className={`needs-validation${validated ? ' was-validated' : ''}`}
                    noValidate
                    method="POST"
                    action="/signup"
                    onSubmit={submit}
                  >
                    <h4 className="mb-4">Account Information</h4>
                    {error && (
                      <div id="signup-error" className="alert alert-danger mb-4" role="alert">
                        <span className="alert-icon mr-2 material-icons error-icon">error</span>{error}
                      </div>
                    )}
                    <div id="alertBanner" className={`alert alert-danger mb-4${mismatch ? '' : ' hidden'}`} role="alert">
                      <span className="alert-icon mr-2 material-icons error-icon">error</span>
                      Passwords don&apos;t match. Please try again.
                    </div>
                    <div className="mb-5">
                      <label className="text-uppercase text-muted secondary-text" htmlFor="signup-username">Username</label>
                      <div className="input-group mt-2 mb-5">
                        <div className="input-group-prepend mr-2">
                          <span className="input-group-text"><span className="material-icons">account_circle</span></span>
                        </div>
                        <input className="form-control" type="text" id="signup-username" name="username" autoComplete="off" pattern="([a-zA-Z0-9_]){2,15}" required />
                        <div className="invalid-feedback">
                          Please enter a valid username. Username must be 2 to 15 characters in length and contain only alphanumeric or underscore characters.
                        </div>
                      </div>
                    </div>

                    <div className="mb-5">
                      <label className="text-uppercase text-muted secondary-text" htmlFor="signup-password">Password</label>
                      <div className="input-group mt-2 mb-5">
                        <div className="input-group-prepend mr-2">
                          <span className="input-group-text"><span className="material-icons">lock</span></span>
                        </div>
                        <input className="form-control" type="password" id="signup-password" name="password" autoComplete="off" required />
                        <div className="invalid-feedback">Please enter a password.</div>
                      </div>
                    </div>

                    <div className="mb-5">
                      <label className="text-uppercase text-muted secondary-text" htmlFor="signup-password-repeat">Confirm Password</label>
                      <div className="input-group mt-2 mb-5">
                        <div className="input-group-prepend mr-2">
                          <span className="input-group-text"><span className="material-icons">lock</span></span>
                        </div>
                        <input className="form-control" type="password" id="signup-password-repeat" name="password-repeat" autoComplete="off" required />
                        <div className="invalid-feedback">Please confirm your password.</div>
                      </div>
                    </div>

                    <h4 className="mb-4">Personal Information</h4>
                    <h6 className="mb-5">Some fields are read-only for this demo for security purposes.</h6>

                    <div className="row mb-5">
                      <div className="col-md-6">
                        <label className="text-uppercase text-muted secondary-text" htmlFor="signup-firstname">First name</label>
                        <input type="text" className="form-control" id="signup-firstname" name="firstname" required />
                        <div className="invalid-feedback">Valid first name is required.</div>
                      </div>
                      <div className="col-md-6">
                        <label className="text-uppercase text-muted secondary-text" htmlFor="signup-lastname">Last name</label>
                        <input type="text" className="form-control" id="signup-lastname" name="lastname" required />
                        <div className="invalid-feedback">Valid last name is required.</div>
                      </div>
                    </div>

                    <div className="mb-5">
                      <label className="text-uppercase text-muted secondary-text" htmlFor="address">Address</label>
                      <input type="text" className="form-control" id="address" name="address" defaultValue="123 Nth Avenue, New York City" readOnly />
                      <div className="invalid-feedback">Please enter your address.</div>
                    </div>

                    <div className="row mb-5">
                      <div className="col-md-5">
                        <label className="text-uppercase text-muted secondary-text" htmlFor="country">Country</label>
                        <select className="custom-select d-block w-100" id="country" name="country" defaultValue="United States">
                          <option>United States</option>
                        </select>
                        <div className="invalid-feedback">Please select a valid country.</div>
                      </div>
                      <div className="col-md-4">
                        <label className="text-uppercase text-muted secondary-text" htmlFor="state">State</label>
                        <select className="custom-select d-block w-100" id="state" name="state" defaultValue={DEFAULT_STATE}>
                          <option value="">Choose...</option>
                          {STATES.map(([code, name]) => (
                            <option key={code} value={code}>{name}</option>
                          ))}
                        </select>
                        <div className="invalid-feedback">Please provide a valid state.</div>
                      </div>
                      <div className="col-md-3">
                        <label className="text-uppercase text-muted secondary-text" htmlFor="zip">Zip</label>
                        <input type="text" className="form-control" id="zip" name="zip" defaultValue="10004" readOnly />
                        <div className="invalid-feedback">Zip code required.</div>
                      </div>
                    </div>

                    <div className="row mb-5">
                      <div className="col-md-6">
                        <label className="text-uppercase text-muted secondary-text" htmlFor="ssn">SSN</label>
                        <input type="text" className="form-control" id="ssn" name="ssn" defaultValue="111-22-3333" readOnly />
                        <div className="invalid-feedback">Valid SSN is required.</div>
                      </div>
                      <div className="col-md-6">
                        <label className="text-uppercase text-muted secondary-text" htmlFor="signup-birthday">Birthday</label>
                        <input type="date" className="form-control" id="signup-birthday" name="birthday" min="1900-01-01" max={today} required />
                        <div className="invalid-feedback">Valid birthday is required.</div>
                      </div>
                    </div>

                    <div className="mb-5">
                      <label className="text-uppercase text-muted secondary-text" htmlFor="timezone">Timezone</label>
                      <select className="custom-select d-block w-100" id="timezone" name="timezone" defaultValue={DEFAULT_TIMEZONE_ID} required>
                        {TIMEZONES.map((zone) => (
                          <option key={zone.id} value={zone.id}>{zone.label}</option>
                        ))}
                      </select>
                      <div className="invalid-feedback">Please select a valid timezone.</div>
                    </div>

                    <hr className="mb-4" />
                    <div className="col-lg-10 offset-lg-1 sign-in">
                      <button className="btn btn-block btn-primary" type="submit" disabled={busy}>Create Account</button>
                    </div>
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
