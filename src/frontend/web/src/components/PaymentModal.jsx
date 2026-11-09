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
import { sendPayment } from '../api.js';
import { uuidv4 } from '../format.js';

const NEW_RECIPIENT = 'add';

/** The form to send a payment from the user's account to a contact or a new recipient. */
export default function PaymentModal({ open, contacts, balance, onClose, onDone }) {
  const recipients = contacts.filter((contact) => !contact.is_external);
  const [selection, setSelection] = useState(null);
  const [validated, setValidated] = useState(false);
  const [uuid, setUuid] = useState(uuidv4);
  const [busy, setBusy] = useState(false);

  const recipient = selection ?? (recipients.length > 0 ? recipients[0].account_num : NEW_RECIPIENT);
  const isNew = recipient === NEW_RECIPIENT;
  const max = balance === null || balance === undefined ? undefined : balance / 100;

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
    const payment = { account_num: recipient, amount: form.elements.amount.value, uuid };
    if (isNew) {
      payment.contact_account_num = form.elements.contact_account_num.value;
      payment.contact_label = form.elements.contact_label.value;
    }
    setBusy(true);
    let outcome;
    try {
      const { message } = await sendPayment(payment);
      outcome = { message, isError: false };
    } catch (err) {
      outcome = { message: err.message, isError: true };
    }
    setBusy(false);
    close();
    onDone(outcome);
  }

  return (
    <Modal id="sendPayment" open={open}>
      <form
        id="payment-form"
        className={`needs-validation${validated ? ' was-validated' : ''}`}
        noValidate
        method="POST"
        action="/payment"
        onSubmit={submit}
      >
        <div className="modal-header">
          <h3 className="modal-title header-title" id="paymentModalTitle">Send a Payment</h3>
          <button type="button" className="close payment-cancel" aria-label="Close" onClick={close}>
            <span aria-hidden="true">&times;</span>
          </button>
        </div>
        <div className="modal-body">
          <div className="row">
            <div className="col-md-10 offset-md-1 mb-4">
              <label className="text-uppercase text-muted secondary-text mb-3" htmlFor="payment-accounts">Recipient</label>
              <select
                className="custom-select d-block w-100 mb-3"
                id="payment-accounts"
                name="account_num"
                value={recipient}
                onChange={(event) => setSelection(event.target.value)}
              >
                {recipients.map((contact) => (
                  <option key={contact.account_num} value={contact.account_num}>
                    {contact.label} - {contact.account_num}
                  </option>
                ))}
                <option disabled>──────────</option>
                <option value={NEW_RECIPIENT}>New Recipient</option>
              </select>
              <div id="otherAccountInputs" className={isNew ? '' : 'hidden'}>
                <div className="input-group mb-3">
                  <div className="input-group-prepend">
                    <span className="input-group-text"><strong className="modal-icon">#</strong></span>
                  </div>
                  <input
                    className="form-control"
                    type="number"
                    step="1"
                    id="contact_account_num"
                    name="contact_account_num"
                    min="1000000000"
                    max="9999999999"
                    placeholder="Account Number"
                    required={isNew}
                  />
                  <div className="invalid-feedback">Please enter a valid 10 digit account number.</div>
                </div>
                <div className="input-group mb-3">
                  <div className="input-group-prepend">
                    <span className="input-group-text"><span className="modal-icon material-icons">label</span></span>
                  </div>
                  <input
                    className="form-control"
                    type="text"
                    id="contact_label"
                    name="contact_label"
                    maxLength="30"
                    pattern="^[0-9a-zA-Z][0-9a-zA-Z ]{0,29}$"
                    placeholder="Contact Label (Optional)"
                  />
                  <div className="invalid-feedback">Invalid label.</div>
                </div>
              </div>
            </div>
            <div className="col-md-10 offset-md-1">
              <label className="text-uppercase text-muted secondary-text mb-3" htmlFor="payment-amount">Transaction Amount</label>
              <div className="input-group mb-3">
                <div className="input-group-prepend mr-2">
                  <span className="input-group-text"><span className="amount-font material-icons">attach_money</span></span>
                </div>
                <input
                  className="form-control amount-font"
                  type="number"
                  autoComplete="off"
                  step="0.01"
                  id="payment-amount"
                  name="amount"
                  placeholder="0.00"
                  min="0.01"
                  max={max}
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
                Send
              </button>
            </div>
          </div>
        </div>
        <input type="hidden" id="payment-uuid" name="uuid" value={uuid} readOnly />
      </form>
    </Modal>
  );
}
