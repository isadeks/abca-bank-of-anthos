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
import { useSearchParams } from 'react-router-dom';
import { sendConsent } from '../api.js';

/** Only follow web addresses: a redirect to javascript: must not run. */
function isWebAddress(url) {
  try {
    return ['http:', 'https:'].includes(new URL(url, window.location.href).protocol);
  } catch {
    return false;
  }
}

export default function Consent() {
  const [params] = useSearchParams();
  const [failed, setFailed] = useState(false);
  const appName = params.get('app_name');
  const state = params.get('state');
  const redirectUri = params.get('redirect_uri');

  async function answer(event, consent) {
    event.preventDefault();
    try {
      const { redirect } = await sendConsent({ consent, state, redirect_uri: redirectUri });
      if (!isWebAddress(redirect)) {
        throw new Error('not a web address');
      }
      window.location.assign(redirect);
    } catch {
      setFailed(true);
    }
  }

  return (
    <main className="container">
      <div className="row mt-5 mb-5">
        <div className="col-lg-6 offset-lg-3">
          <div className="card">
            <div className="card-title header-body">
              <div className="text-center col-10 offset-1">
                <p className="text-muted secondary-text">
                  &quot;{appName}&quot; is requesting access to your account information
                </p>
                <h2 className="mb-4 header-title">Do you consent?</h2>
              </div>
            </div>
            <div className="card-body sign-in">
              <div className="row align-items-center mt-2">
                <div className="col-10 offset-1 mb-4">
                  {failed && (
                    <div id="alertBanner" className="alert alert-danger mb-4" role="alert">
                      <span className="error-icon mr-2 material-icons">error</span>
                      The request could not be completed.
                    </div>
                  )}
                  <form id="consent-form" className="needs-validation" noValidate>
                    <button
                      className="btn btn-sign-in btn-block mb-4"
                      type="submit"
                      onClick={(event) => answer(event, true)}
                    >
                      Approve
                    </button>
                    <button
                      className="btn btn-deny btn-block mb-4"
                      type="submit"
                      onClick={(event) => answer(event, false)}
                    >
                      Deny
                    </button>
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
