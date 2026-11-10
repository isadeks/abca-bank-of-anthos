/*
 * Copyright 2026 Google Inc. All Rights Reserved.
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

// Light / dark mode. Loaded in <head> so the theme is applied before the page
// is painted. The choice is kept in localStorage; without one, the browser's
// preferred color scheme is used.
(function() {
  var KEY = "theme";

  function stored() {
    try {
      var value = window.localStorage.getItem(KEY);
      return (value === "dark" || value === "light") ? value : null;
    } catch (e) {
      return null;
    }
  }

  function preferred() {
    return stored() ||
      ((window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light");
  }

  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    var button = document.getElementById("theme-toggle");
    if (button) {
      var dark = theme === "dark";
      var label = dark ? "Switch to light mode" : "Switch to dark mode";
      button.setAttribute("aria-pressed", dark ? "true" : "false");
      button.setAttribute("aria-label", label);
      button.setAttribute("title", label);
      button.querySelector(".material-icons").textContent = dark ? "light_mode" : "dark_mode";
    }
  }

  apply(preferred());

  document.addEventListener("DOMContentLoaded", function() {
    apply(document.documentElement.getAttribute("data-theme"));
    var button = document.getElementById("theme-toggle");
    if (!button) {
      return;
    }
    button.addEventListener("click", function() {
      var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      try {
        window.localStorage.setItem(KEY, next);
      } catch (e) {
        // Storage unavailable: the choice applies to this page only.
      }
      apply(next);
    });
  });
})();
