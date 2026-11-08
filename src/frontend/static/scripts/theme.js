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

// Dark mode toggle: switches the theme in place and remembers the choice in
// the "theme" cookie, which the server reads to render the next page.
document.addEventListener("DOMContentLoaded", function() {
  var toggle = document.querySelector("#theme-toggle");
  if (!toggle) {
    return;
  }
  var icon = document.querySelector("#theme-toggle-icon");
  toggle.addEventListener("click", function() {
    var root = document.documentElement;
    var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    toggle.setAttribute("aria-pressed", next === "dark" ? "true" : "false");
    icon.textContent = next === "dark" ? "light_mode" : "dark_mode";
    document.cookie = "theme=" + next + "; path=/; max-age=31536000; SameSite=Lax";
  });
});
