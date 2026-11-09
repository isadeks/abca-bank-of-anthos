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
import Modal from './Modal.jsx';
import { sendDeposit } from '../api.js';
import { uuidv4 } from '../format.js';

const NEW_ACCOUNT = 'add';

function accountValue(account) {
  return JSON.stringify({ account_num: account.account_num, routing_num: account.routing_num });
}

/** The form to deposit funds from an external account into the user's account. */
export default function DepositModal({ open, contacts, onClose, onDone }) {
  const external = contacts.filter((contact) => contact.is_external);
  const [selection, setSelection] = useState(null);
  const [validated, setValidated] = useState(false);
  const [uuid, setUuid] = useState(uuidv4);
  const [busy, setBusy] = useState(false);

  const account = selection ?? (external.length > 0 ? accountValue(external[0]) : NEW_ACCOUNT);
  const isNew = account === NEW_ACCOUNT;

  function close() {
    setSelection(null);
    setValidated(false);
    setUuid(uuidv4());
    onClose();
  }

  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    setValidated(true);
    if (!form.checkValidity() || Number(form.elements.amount.value) <= 0) {
      return;
    }
    const deposit = { account, amount: form.elements.amount.value, uuid };
    if (isNew) {
      deposit.external_account_num = form.elements.external_account_num.value;
      deposit.external_routing_num = form.elements.external_routing_num.value;
      deposit.external_label = form.elements.external_label.value;
    }
    setBusy(true);
    let outcome;
    try {
      const { message } = await sendDeposit(deposit);
      outcome = { message, isError: false };
    } catch (err) {
      outcome = { message: err.message, isError: true };
    }
    setBusy(false);
    close();
    onDone(outcome);
  }

  return (
    <Modal id="depositFunds" open={open}>
      <form
        id="deposit-form"
        className={`needs-validation${validated ? ' was-validated' : ''}`}
        noValidate
        method="POST"
        action="/deposit"
        onSubmit={submit}
      >
        <div className="modal-header">
          <h3 className="modal-title header-title" id="depositModalTitle">Make a Deposit</h3>
          <button type="button" className="close deposit-cancel" aria-label="Close" onClick={close}>
            <span aria-hidden="true">&times;</span>
          </button>
        </div>
        <div className="modal-body">
          <div className="row">
            <div className="col-md-10 offset-md-1 mb-4">
              <label className="text-uppercase text-muted secondary-text mb-3" htmlFor="accounts">External Account</label>
              <select
                className="custom-select d-block w-100"
                id="accounts"
                name="account"
                value={account}
                onChange={(event) => setSelection(event.target.value)}
              >
                {external.map((contact) => (
                  <option key={`${contact.account_num}-${contact.routing_num}`} value={accountValue(contact)}>
                    {contact.label} - {contact.account_num} - {contact.routing_num}
                  </option>
                ))}
                <option disabled>──────────</option>
                <option value={NEW_ACCOUNT}>New External Account</option>
              </select>
              <div id="otherDepositInputs" className={isNew ? '' : 'hidden'}>
                <div id="alertBanner" className="alert alert-danger mt-3 mb-3" role="alert">
                  <span className="error-icon mr-2 material-icons">error</span>
                  <strong>Warning</strong>: This website is a simulation. Please don&apos;t include real personal information.
                </div>
                <div className="input-group mb-3">
                  <div className="input-group-prepend">
                    <span className="input-group-text"><strong className="modal-icon">#</strong></span>
                  </div>
                  <input
                    className="form-control"
                    type="number"
                    step="1"
                    id="external_account_num"
                    name="external_account_num"
                    min="1000000000"
                    max="9999999999"
                    placeholder="Account Number"
                    required={isNew}
                  />
                  <div className="invalid-feedback">Please enter a valid 10 digit account number.</div>
                </div>
                <div className="input-group mb-3">
                  <div className="input-group-prepend">
                    <span className="input-group-text"><span className="modal-icon material-icons">account_balance</span></span>
                  </div>
                  <input
                    className="form-control"
                    type="number"
                    step="1"
                    id="external_routing_num"
                    name="external_routing_num"
                    min="100000000"
                    max="999999999"
                    placeholder="Routing Number"
                    required={isNew}
                  />
                  <div className="invalid-feedback">Please enter a valid 9 digit routing number.</div>
                </div>
                <div className="input-group mb-3">
                  <div className="input-group-prepend">
                    <span className="input-group-text"><span className="modal-icon material-icons">label</span></span>
                  </div>
                  <input
                    className="form-control"
                    type="text"
                    id="external_label"
                    maxLength="30"
                    pattern="^[0-9a-zA-Z][0-9a-zA-Z ]{0,29}$"
                    name="external_label"
                    placeholder="Account Label (Optional)"
                  />
                  <div className="invalid-feedback">Invalid label.</div>
                </div>
              </div>
            </div>
            <div className="col-md-10 offset-md-1">
              <label className="text-uppercase text-muted secondary-text mb-1" htmlFor="deposit-amount">Deposit Amount</label>
              <div className="input-group mb-3">
                <div className="input-group-prepend mr-2">
                  <span className="input-group-text"><span className="amount-font material-icons money-icon">attach_money</span></span>
                </div>
                <input
                  className="form-control amount-font"
                  type="number"
                  autoComplete="off"
                  step="0.01"
                  id="deposit-amount"
                  name="amount"
                  placeholder="0.00"
                  min="0.01"
                  max="500000.00"
                  required
                />
                <div className="invalid-feedback">Please enter a valid amount.</div>
              </div>
            </div>
          </div>
        </div>
        <div className="modal-body">
          <div className="row align-items-end text-right">
            <div className="col-md-10 offset-md-1 text-right align-items-end">
              <button type="button" className="btn btn-secondary" onClick={close}>Cancel</button>
              <button type="submit" className="btn btn-primary btn-with-padding deposit-send-button" disabled={busy}>
                Deposit
              </button>
            </div>
          </div>
        </div>
        <input type="hidden" id="deposit-uuid" name="uuid" value={uuid} readOnly />
      </form>
    </Modal>
  );
}
