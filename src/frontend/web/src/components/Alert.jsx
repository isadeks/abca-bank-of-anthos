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
 * The banner above the home page that reports the outcome of a payment or a
 * deposit. `message` is { message, isError }; nothing is shown without one.
 */
export default function Alert({ message, onClose }) {
  if (!message) {
    return null;
  }
  const { message: text, isError } = message;
  return (
    <div
      className="row col-lg-12 align-items-start"
      id="alert-message-div"
      role={isError ? 'alert' : undefined}
    >
      <div className="col-lg">
        <div className={`card snackbar-card${isError ? ' border-danger alert-message-error' : ''}`}>
          <div className="card-body snackbar-body">
            <div className="row align-items-center">
              <div className="col">
                <h5
                  id="alert-message"
                  className={`alert-message-container${isError ? ' text-danger' : ''}`}
                >
                  <div className="check-mark-container">
                    <span className="snackbar-close material-icons">{isError ? 'error' : 'check_circle'}</span>
                  </div>
                  {text}
                </h5>
              </div>
              <div className="button-icon col-auto">
                <span
                  className="snackbar-close material-icons"
                  role="button"
                  aria-label="Dismiss"
                  onClick={onClose}
                >
                  close
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
