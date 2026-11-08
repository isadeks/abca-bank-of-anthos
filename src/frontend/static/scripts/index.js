/*
 * Copyright 2023 Google Inc. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
 
document.addEventListener("DOMContentLoaded", function(event) {
  // Deposit modal client-side validation
  var depositForm = document.querySelector("#deposit-form");
  depositForm.addEventListener("submit", function(e) {
    var isNewAcct = (document.querySelector("#accounts").value == "add");
    document.querySelector("#external_account_num").required = isNewAcct;
    document.querySelector("#external_routing_num").required = isNewAcct;

    if(!depositForm.checkValidity() || document.querySelector("#deposit-amount").value <= 0.00){
      e.preventDefault();
      e.stopPropagation();
    }
    depositForm.classList.add("was-validated");
  });

  // Reset form on cancel event
  document.querySelectorAll(".deposit-cancel").forEach((depositCancel) => {
    depositCancel.addEventListener("click", function () {
      depositForm.reset();
      depositForm.classList.remove("was-validated");
      RefreshModals();
    });
  });

  // Send payment modal client-side validation
  var paymentForm = document.querySelector("#payment-form");
  paymentForm.addEventListener("submit", function(e) {
    // Check if account number is required
    document.querySelector("#contact_account_num").required = (document.querySelector("#payment-accounts").value == "add");

    if(!paymentForm.checkValidity() || document.querySelector("#payment-amount").value <= 0.00){
      e.preventDefault();
      e.stopPropagation();
    }
    paymentForm.classList.add("was-validated");
  });

  // Reset form on cancel event
  document.querySelectorAll(".payment-cancel").forEach((paymentCancel) => {
    paymentCancel.addEventListener("click", function () {
      paymentForm.reset();
      paymentForm.classList.remove("was-validated");
      RefreshModals();
    });
  });

  // Budget warning: before a payment is sent, ask the server whether it would
  // push this month's spending over the monthly limit. The payment is still
  // allowed after the user confirms. Any problem with the check lets the
  // payment go through as before.
  var budgetWarning = document.querySelector("#budget-warning");
  var paymentButtons = document.querySelector("#payment-buttons");

  function formatDollars(cents) {
    return "$" + (cents / 100).toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
  }

  function resetBudgetWarning() {
    budgetWarning.classList.add("hidden");
    paymentButtons.classList.remove("hidden");
  }

  function showBudgetWarning(check) {
    document.querySelector("#budget-warning-text").textContent =
      "this payment of " + formatDollars(check.amount_cents) + " would bring this month's spending to " +
      formatDollars(check.after_cents) + ", over your monthly budget of " + formatDollars(check.limit_cents) + ".";
    paymentButtons.classList.add("hidden");
    budgetWarning.classList.remove("hidden");
  }

  paymentForm.addEventListener("submit", function(e) {
    if (e.defaultPrevented || paymentForm.dataset.budgetCheck !== "true") {
      return;
    }
    e.preventDefault();
    var amount = document.querySelector("#payment-amount").value;
    fetch("/budget/check?amount=" + encodeURIComponent(amount), {credentials: "same-origin"})
      .then(function(resp) { return resp.ok ? resp.json() : {exceeds: false}; })
      .catch(function() { return {exceeds: false}; })
      .then(function(check) {
        if (check.exceeds) {
          showBudgetWarning(check);
        } else {
          paymentForm.submit();
        }
      });
  });

  document.querySelector("#budget-warning-confirm").addEventListener("click", function() {
    paymentForm.submit();
  });

  document.querySelector("#budget-warning-cancel").addEventListener("click", function() {
    resetBudgetWarning();
  });

  // Handle new account option in Send Payment modal
  document.querySelector("#payment-accounts").addEventListener("change", function(e) {
    RefreshModals();
  });

  // Handle new account option in Deposit modal
  document.querySelector("#accounts").addEventListener("change", function(e) {
    RefreshModals();
  });


  function uuidv4() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  };


  // Reset Modals to proper state
  function RefreshModals(){
      paymentSelection = document.querySelector("#payment-accounts").value;
      if (paymentSelection == "add") {
        document.querySelector("#otherAccountInputs").classList.remove("hidden");
      } else {
        document.querySelector("#otherAccountInputs").classList.add("hidden");
      }
      depositSelection = document.querySelector("#accounts").value;
      if (depositSelection == "add") {
        document.querySelector("#otherDepositInputs").classList.remove("hidden");
      } else {
        document.querySelector("#otherDepositInputs").classList.add("hidden");
      }
      resetBudgetWarning();
      // generate new uuids
      document.querySelector("#payment-uuid").value = uuidv4();
      document.querySelector("#deposit-uuid").value = uuidv4();
  }
  RefreshModals();
});
