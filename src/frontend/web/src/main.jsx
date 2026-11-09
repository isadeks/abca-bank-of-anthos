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

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App.jsx';
import './platform.css';
import './cymbal.css';

/**
 * The message of a failed form post, which the Flask service puts in the page.
 * Read it before React replaces what is in #root.
 */
function readFlash() {
  const element = document.getElementById('boa-flash');
  if (!element) {
    return null;
  }
  try {
    return JSON.parse(element.textContent);
  } catch {
    return null;
  }
}

const flash = readFlash();

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App flash={flash} />
    </BrowserRouter>
  </StrictMode>,
);
