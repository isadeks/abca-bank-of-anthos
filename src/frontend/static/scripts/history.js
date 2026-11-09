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

// "Load more" for the transaction history: fetches the next page of rows
// from /history and appends them to the table.
document.addEventListener("DOMContentLoaded", function () {
  var button = document.querySelector("#load-more-transactions");
  if (!button) {
    return;
  }
  var tbody = document.querySelector("#transaction-list");
  var label = button.textContent;

  button.addEventListener("click", function () {
    button.disabled = true;
    button.textContent = "Loading...";
    fetch("history?offset=" + encodeURIComponent(button.dataset.nextOffset), {
      credentials: "same-origin",
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("HTTP " + response.status);
        }
        return response.json();
      })
      .then(function (page) {
        tbody.insertAdjacentHTML("beforeend", page.html);
        button.dataset.nextOffset = page.next_offset;
        if (page.has_more) {
          button.disabled = false;
          button.textContent = label;
        } else {
          document.querySelector("#load-more-container").remove();
        }
      })
      .catch(function () {
        button.disabled = false;
        button.textContent = "Could not load more - try again";
      });
  });
});
