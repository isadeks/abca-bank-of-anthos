/*
 * Copyright 2026 Google LLC
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

// Accessibility helpers shared by the login, payment and deposit forms.
(function (window, document) {
  var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), ' +
    'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function isVisible(el) {
    return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  }

  function focusableIn(container) {
    return Array.prototype.filter.call(container.querySelectorAll(FOCUSABLE), isVisible);
  }

  // Link every input to its ".invalid-feedback" message and keep aria-invalid /
  // aria-describedby in sync with the input's current validity, so that a
  // screen reader reads the error when the field gets focus.
  function syncFieldErrors(form) {
    var firstInvalid = null;
    form.querySelectorAll("input, select").forEach(function (input) {
      var group = input.closest(".input-group");
      var feedback = group && group.querySelector(".invalid-feedback");
      if (!feedback || !input.id) {
        return;
      }
      if (!feedback.id) {
        feedback.id = input.id + "-error";
      }
      var invalid = isVisible(input) && !input.checkValidity();
      if (invalid) {
        input.setAttribute("aria-invalid", "true");
        input.setAttribute("aria-describedby", feedback.id);
        firstInvalid = firstInvalid || input;
      } else {
        input.removeAttribute("aria-invalid");
        input.removeAttribute("aria-describedby");
      }
    });
    return firstInvalid;
  }

  // After a failed submit: expose the errors and move focus to the first
  // invalid field. Keeps the error messages current while the user corrects them.
  function reportInvalid(form) {
    var firstInvalid = syncFieldErrors(form);
    if (!form.hasAttribute("data-a11y-live")) {
      form.setAttribute("data-a11y-live", "true");
      form.addEventListener("input", function () { syncFieldErrors(form); });
      form.addEventListener("change", function () { syncFieldErrors(form); });
    }
    if (firstInvalid) {
      firstInvalid.focus();
    }
  }

  function clearFieldErrors(form) {
    form.querySelectorAll("[aria-invalid]").forEach(function (input) {
      input.removeAttribute("aria-invalid");
      input.removeAttribute("aria-describedby");
    });
  }

  // Modal dialogs: move focus in when opened, keep Tab / Shift+Tab inside
  // while open, and give focus back to the control that opened the dialog.
  function setupModal(modal) {
    var opener = null;
    var $modal = window.jQuery(modal);

    $modal.on("show.bs.modal", function (e) {
      opener = e.relatedTarget || document.activeElement;
    });
    $modal.on("shown.bs.modal", function () {
      var fields = focusableIn(modal.querySelector(".modal-body") || modal);
      (fields[0] || modal).focus();
    });
    $modal.on("hidden.bs.modal", function () {
      if (opener && typeof opener.focus === "function") {
        opener.focus();
      }
      opener = null;
    });
    modal.addEventListener("keydown", function (e) {
      if (e.key !== "Tab") {
        return;
      }
      var items = focusableIn(modal);
      if (!items.length) {
        e.preventDefault();
        return;
      }
      var first = items[0];
      var last = items[items.length - 1];
      var active = document.activeElement;
      if (e.shiftKey && (active === first || active === modal)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      } else if (items.indexOf(active) === -1) {
        e.preventDefault();
        first.focus();
      }
    });
  }

  // Make a non-native control (e.g. a clickable card) operable by keyboard.
  function makeButton(el) {
    el.setAttribute("role", "button");
    el.setAttribute("tabindex", "0");
    el.addEventListener("keydown", function (e) {
      if (e.target === el && (e.key === "Enter" || e.key === " " || e.key === "Spacebar")) {
        e.preventDefault();
        el.click();
      }
    });
  }

  window.A11y = {
    syncFieldErrors: syncFieldErrors,
    reportInvalid: reportInvalid,
    clearFieldErrors: clearFieldErrors,
    setupModal: setupModal,
    makeButton: makeButton
  };
})(window, document);
