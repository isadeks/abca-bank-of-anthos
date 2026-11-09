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

  // Handle new account option in Send Payment modal
  document.querySelector("#payment-accounts").addEventListener("change", function(e) {
    RefreshModals();
  });

  // Handle new account option in Deposit modal
  document.querySelector("#accounts").addEventListener("change", function(e) {
    RefreshModals();
  });


  // Split a bill modal: pick contacts + total, review the summary, then send
  var splitForm = document.querySelector("#split-form");
  var splitError = document.querySelector("#split-error");

  function formatCents(cents) {
    return "$" + (cents / 100).toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
  }

  function showSplitStep(step) {
    document.querySelector("#split-step-pick").classList.toggle("hidden", step != "pick");
    document.querySelector("#split-step-summary").classList.toggle("hidden", step != "summary");
  }

  function showSplitError(message) {
    splitError.textContent = message;
    splitError.classList.remove("hidden");
  }

  function resetSplit() {
    splitForm.reset();
    splitError.classList.add("hidden");
    showSplitStep("pick");
    RefreshModals();
  }

  document.querySelector("#split-review").addEventListener("click", function() {
    splitError.classList.add("hidden");
    var picked = document.querySelectorAll(".split-contact:checked").length;
    var amount = document.querySelector("#split-amount");
    if (picked < 2 || picked > 4) {
      showSplitError("Pick 2 to 4 contacts.");
      return;
    }
    if (!amount.checkValidity() || amount.value <= 0) {
      showSplitError("Please enter a valid amount.");
      return;
    }
    // The server works out the shares, so the summary is what will be sent
    fetch("/split/preview", {method: "POST", body: new URLSearchParams(new FormData(splitForm)), credentials: "same-origin"})
      .then(function(resp) { return resp.json().then(function(body) { return {ok: resp.ok, body: body}; }); })
      .then(function(result) {
        if (!result.ok) {
          showSplitError("Split failed: " + (result.body.error || "unknown error"));
          return;
        }
        var rows = document.querySelector("#split-summary-rows");
        rows.innerHTML = "";
        result.body.shares.forEach(function(share) {
          var row = rows.insertRow();
          row.className = "split-summary-row";
          row.insertCell().textContent = share.label + " (" + share.account_num + ")";
          var cell = row.insertCell();
          cell.className = "text-right";
          cell.textContent = formatCents(share.amount);
        });
        document.querySelector("#split-summary-total").textContent = formatCents(result.body.total);
        showSplitStep("summary");
      })
      .catch(function() { showSplitError("Split failed: could not reach the server."); });
  });

  document.querySelector("#split-back").addEventListener("click", function() {
    showSplitStep("pick");
  });

  document.querySelectorAll(".split-cancel").forEach(function(cancel) {
    cancel.addEventListener("click", resetSplit);
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
      // generate new uuids
      document.querySelector("#payment-uuid").value = uuidv4();
      document.querySelector("#deposit-uuid").value = uuidv4();
      document.querySelector("#split-uuid").value = uuidv4();
  }
  RefreshModals();
});
