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

import { useEffect } from 'react';

/**
 * A Bootstrap modal dialog that stays in the page while it is closed.
 * It does not close on Escape or on a click outside, like the forms it
 * replaces: only the form's own buttons close it.
 */
export default function Modal({ id, open, children }) {
  useEffect(() => {
    document.body.classList.toggle('modal-open', open);
    return () => document.body.classList.remove('modal-open');
  }, [open]);

  return (
    <>
      <div
        className={`modal fade${open ? ' show' : ''}`}
        id={id}
        tabIndex="-1"
        role="dialog"
        aria-hidden={!open}
        style={open ? { display: 'block' } : undefined}
      >
        <div className="modal-dialog modal-dialog-centered" role="document">
          <div className="modal-content">{children}</div>
        </div>
      </div>
      {open && <div className="modal-backdrop fade show"></div>}
    </>
  );
}
