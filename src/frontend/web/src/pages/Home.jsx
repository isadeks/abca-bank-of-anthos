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
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../AppContext.jsx';
import { ApiError, getHome } from '../api.js';
import { formatCurrency } from '../format.js';
import Alert from '../components/Alert.jsx';
import DepositModal from '../components/DepositModal.jsx';
import PaymentModal from '../components/PaymentModal.jsx';
import TransactionTable from '../components/TransactionTable.jsx';

export default function Home({ flash = null, onFlashShown = () => {} }) {
  const { setSession } = useApp();
  const navigate = useNavigate();
  const [home, setHome] = useState(null);
  const [failed, setFailed] = useState(false);
  const [message, setMessage] = useState(flash);
  const [modal, setModal] = useState(null);

  const load = useCallback(async () => {
    try {
      setHome(await getHome());
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setSession(null);
        navigate('/login');
      } else {
        setFailed(true);
      }
    }
  }, [navigate, setSession]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (flash) {
      setMessage(flash);
      onFlashShown();
    }
  }, [flash, onFlashShown]);

  async function done(outcome) {
    setModal(null);
    setMessage(outcome);
    await load();
  }

  if (failed) {
    return (
      <main className="container">
        <div className="alert alert-danger mt-5" role="alert">
          The account could not be loaded. Please try again later.
        </div>
      </main>
    );
  }
  if (!home) {
    return <main className="container"></main>;
  }

  return (
    <main className="container">
      <Alert message={message} onClose={() => setMessage(null)} />

      <div className="row col-lg-12 align-items-start top-row">
        <div className="col-md-8">
          <small className="text-uppercase text-muted secondary-text">Overview</small>
          <h2 className="header-title">Checking Account</h2>
        </div>
        <div className="col-md-4 account-info text-right">
          <p>
            <span className="account-overview account-icon material-icons">info</span>
            <span className="account-num-text">Account Number:</span>
            <span className="account-number">{home.account_id}</span>
          </p>
        </div>
      </div>

      <div className="row col-lg-12 align-items-start">
        <div className="col-lg-4">
          <div className="card">
            <div className="card-body">
              <div className="row align-items-start">
                <div className="col">
                  <p className="text-uppercase mb-3">
                    <b className="current-balance">Current Balance</b>
                  </p>
                  <span className="h1 mb-0" id="current-balance">{formatCurrency(home.balance)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="col-lg-4 deposit-send-payment-div">
          <div className="card card-button deposit-send-button" onClick={() => setModal('deposit')}>
            <div className="card-body">
              <div className="row align-items-start">
                <div className="col"><span className="h5 mb-0" id="depositSpan">Deposit Funds</span></div>
                <div className="button-icon col-auto">
                  <span className="material-icons" id="deposit-icon">get_app</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className="col-lg-4 deposit-send-payment-div">
          <div className="card card-button deposit-send-button" onClick={() => setModal('payment')}>
            <div className="card-body">
              <div className="row align-items-start">
                <div className="col"><span className="h5 mb-0" id="paymentSpan">Send Payment</span></div>
                <div className="button-icon col-auto">
                  <span className="material-icons" id="payment-icon">forward</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="row col-lg-12 mb-4 align-items-start">
          <div className="col-lg-12">
            <div className="card transaction-card">
              <div className="card-table-header">
                <div className="row align-items-start">
                  <div className="col"><h4 className="card-header-title">Transaction History</h4></div>
                </div>
              </div>
              <TransactionTable accountId={home.account_id} history={home.history} />
            </div>
          </div>
        </div>

        <DepositModal
          open={modal === 'deposit'}
          contacts={home.contacts}
          onClose={() => setModal(null)}
          onDone={done}
        />
        <PaymentModal
          open={modal === 'payment'}
          contacts={home.contacts}
          balance={home.balance}
          onClose={() => setModal(null)}
          onDone={done}
        />
      </div>
    </main>
  );
}
