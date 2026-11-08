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
  var paymentConfirm = document.querySelector("#payment-confirm");
  var largePaymentThreshold = parseFloat(paymentConfirm.dataset.threshold);

  // Show the payment form (true) or the large payment confirmation step (false)
  function showPaymentDetails(show) {
    document.querySelectorAll(".payment-step").forEach(function(step) {
      step.classList.toggle("hidden", !show);
    });
    paymentConfirm.classList.toggle("hidden", show);
  }

  // Describe the recipient as shown in the dropdown, or the typed account number
  function paymentRecipient() {
    var select = document.querySelector("#payment-accounts");
    if (select.value == "add") {
      var label = document.querySelector("#contact_label").value.trim();
      var num = document.querySelector("#contact_account_num").value;
      return label ? label + " - " + num : num;
    }
    return select.options[select.selectedIndex].text;
  }

  paymentForm.addEventListener("submit", function(e) {
    // Check if account number is required
    document.querySelector("#contact_account_num").required = (document.querySelector("#payment-accounts").value == "add");

    var amount = parseFloat(document.querySelector("#payment-amount").value);
    if(!paymentForm.checkValidity() || document.querySelector("#payment-amount").value <= 0.00){
      e.preventDefault();
      e.stopPropagation();
    } else if (amount > largePaymentThreshold) {
      // Ask the user to confirm large payments before they are submitted
      e.preventDefault();
      e.stopPropagation();
      document.querySelector("#payment-confirm-message").textContent =
        "You are about to send $" + amount.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2}) +
        " to " + paymentRecipient();
      showPaymentDetails(false);
    }
    paymentForm.classList.add("was-validated");
  });

  // Back from the confirmation step to the payment form
  document.querySelector("#payment-confirm-back").addEventListener("click", function() {
    showPaymentDetails(true);
  });

  // Always reopen the payment modal on the payment form, however it was closed
  if (window.jQuery) {
    window.jQuery("#sendPayment").on("hidden.bs.modal", function() {
      showPaymentDetails(true);
    });
  }

  // Confirmed: submit the payment (form.submit() does not re-run the submit handler)
  document.querySelector("#payment-confirm-send").addEventListener("click", function() {
    paymentForm.submit();
  });

  // Reset form on cancel event
  document.querySelectorAll(".payment-cancel").forEach((paymentCancel) => {
    paymentCancel.addEventListener("click", function () {
      paymentForm.reset();
      paymentForm.classList.remove("was-validated");
      showPaymentDetails(true);
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
  }
  RefreshModals();
});
